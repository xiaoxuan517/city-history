from __future__ import annotations

from pathlib import Path
from threading import Lock
from threading import Thread
from time import monotonic
from typing import Any
from uuid import NAMESPACE_URL
from uuid import uuid4
from uuid import uuid5
from urllib.parse import quote
from urllib.parse import unquote
from urllib.parse import urlparse

import httpx

from app.api.errors import ApiError
from app.config.settings import settings
from app.schemas.alist import (
    AListFileItem,
    AListFileListRequest,
    AListFileListResponse,
    AListOfflineDownloadRequest,
    AListOfflineDownloadResponse,
    AListRawResponse,
    AListTask,
    AListTaskListRequest,
    AListTaskListResponse,
)

_TOKEN_TTL_SECONDS = 47 * 60 * 60
_FILE_LIST_CACHE_TTL_SECONDS = 10 * 60
_TOKEN_CACHE: dict[str, tuple[str, float]] = {}
_TOKEN_CACHE_LOCK = Lock()
_FILE_LIST_CACHE: dict[str, tuple[AListFileListResponse, float]] = {}
_FILE_META_CACHE: dict[str, AListFileItem] = {}
_FILE_CACHE_LOCK = Lock()
_LOCAL_DOWNLOAD_TASKS: dict[str, AListTask] = {}
_LOCAL_DOWNLOAD_FILES: dict[str, Path] = {}
_LOCAL_DOWNLOAD_LOCK = Lock()
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DOWNLOAD_DIR = PROJECT_ROOT / "downloads"
PICTURE_DIR = PROJECT_ROOT / "picture"


class AListService:
    def __init__(
        self,
        *,
        base_url: str | None = None,
        username: str | None = None,
        password: str | None = None,
        client_id: str | None = None,
        timeout: float = 15.0,
    ) -> None:
        self._base_url = (base_url or settings.alist_base_url or "").rstrip("/")
        self._username = username or settings.alist_username or ""
        self._password = password or settings.alist_password or ""
        self._client_id = client_id or settings.alist_client_id
        self._timeout = timeout
        self._token: str | None = None
        self._token_expires_at = 0.0

    def list_files(self, payload: AListFileListRequest) -> AListFileListResponse:
        if not self._base_url:
            raise ApiError(
                status_code=500,
                code="alist_not_configured",
                message="ALIST_BASE_URL is not configured",
            )

        cached_response = self._get_cached_file_list(payload)
        if cached_response is not None:
            return cached_response

        try:
            with self._build_client() as client:
                response = self._post_file_list(client, payload)
        except httpx.HTTPError as exc:
            raise ApiError(
                status_code=502,
                code="alist_request_failed",
                message=f"Failed to request AList: {exc}",
            ) from exc

        try:
            raw_payload = response.json()
            raw_response = AListRawResponse.model_validate(raw_payload)
        except (ValueError, TypeError) as exc:
            raise ApiError(
                status_code=502,
                code="alist_invalid_response",
                message="AList returned an invalid JSON response",
            ) from exc

        if response.status_code >= 400:
            if response.status_code in {401, 403}:
                self._clear_token()
            raise ApiError(
                status_code=502,
                code="alist_request_failed",
                message=raw_response.message or f"AList request failed with status {response.status_code}",
            )

        if raw_response.code != 200:
            if self._is_auth_failure(raw_response):
                self._clear_token()
            raise ApiError(
                status_code=502,
                code="alist_request_failed",
                message=raw_response.message or f"AList request failed with code {raw_response.code}",
            )

        try:
            parsed_response = AListFileListResponse.model_validate(raw_payload)
        except Exception as exc:
            raise ApiError(
                status_code=502,
                code="alist_invalid_response",
                message="AList response format does not match expected schema",
            ) from exc
        self._cache_file_list(payload, parsed_response)
        return parsed_response

    def add_offline_download(self, payload: AListOfflineDownloadRequest) -> AListOfflineDownloadResponse:
        if not self._base_url:
            raise ApiError(
                status_code=500,
                code="alist_not_configured",
                message="ALIST_BASE_URL is not configured",
            )

        if not payload.urls:
            return self._add_local_download(payload)

        urls = payload.urls
        request_payload = {
            "path": payload.path,
            "urls": urls,
            "tool": payload.tool,
            "delete_policy": payload.delete_policy,
        }

        try:
            with self._build_client() as client:
                response = self._post_with_auth(client, "/api/fs/add_offline_download", json=request_payload)
        except httpx.HTTPError as exc:
            raise ApiError(
                status_code=502,
                code="alist_request_failed",
                message=f"Failed to add AList offline download: {exc}",
            ) from exc

        return self._parse_response(response, AListOfflineDownloadResponse, code="alist_download_failed")

    def list_offline_download_tasks(self, payload: AListTaskListRequest) -> AListTaskListResponse:
        tasks: list[AListTask] = []
        local_tasks = self._get_local_tasks(payload.task_ids)
        tasks.extend(local_tasks)
        remote_task_ids = [task_id for task_id in payload.task_ids if task_id not in {task.id for task in local_tasks}]
        if payload.task_ids and not remote_task_ids:
            return AListTaskListResponse(code=200, message="success", data={"tasks": tasks})

        try:
            with self._build_client() as client:
                if remote_task_ids:
                    for task_id in remote_task_ids:
                        task = self._get_task_info(client, task_id)
                        if task is None:
                            task = self._find_task_in_buckets(client, task_id)
                        if task is not None:
                            tasks.append(task)
                else:
                    tasks.extend(self._list_tasks(client, "undone"))
                    tasks.extend(self._list_tasks(client, "done"))
        except httpx.HTTPError as exc:
            raise ApiError(
                status_code=502,
                code="alist_request_failed",
                message=f"Failed to query AList offline download tasks: {exc}",
            ) from exc

        return AListTaskListResponse(
            code=200,
            message="success",
            data={"tasks": tasks},
        )

    def _add_local_download(self, payload: AListOfflineDownloadRequest) -> AListOfflineDownloadResponse:
        source_path = payload.source_path or self._join_path(payload.list_path or "", payload.name or "")
        download_url = self._build_cached_file_download_url(payload)
        filename = self._download_filename(payload, source_path, download_url)
        download_dir = self._local_download_dir(payload.path)
        download_dir.mkdir(parents=True, exist_ok=True)
        existing_task = self.get_existing_local_download_task(filename, download_dir=download_dir)
        if existing_task is not None:
            return AListOfflineDownloadResponse(code=200, message="success", data={"tasks": [existing_task]})
        target_path = self._unique_download_path(download_dir / filename)

        task_id = f"local-{uuid4().hex}"
        task = AListTask(
            id=task_id,
            name=f"download {source_path} to ({target_path})",
            state=0,
            status="queued",
            progress=0,
            error="",
        )
        with _LOCAL_DOWNLOAD_LOCK:
            _LOCAL_DOWNLOAD_TASKS[task_id] = task
            _LOCAL_DOWNLOAD_FILES[task_id] = target_path

        thread = Thread(
            target=self._run_local_download,
            args=(task_id, download_url, target_path),
            daemon=True,
        )
        thread.start()
        return AListOfflineDownloadResponse(code=200, message="success", data={"tasks": [task]})

    def _run_local_download(self, task_id: str, download_url: str, target_path: Path) -> None:
        self._update_local_task(task_id, state=1, status="downloading", progress=0)
        try:
            with httpx.Client(timeout=None, follow_redirects=True) as client:
                with client.stream("GET", download_url) as response:
                    response.raise_for_status()
                    total = int(response.headers.get("content-length") or 0)
                    downloaded = 0
                    with target_path.open("wb") as file:
                        for chunk in response.iter_bytes(chunk_size=1024 * 1024):
                            if not chunk:
                                continue
                            file.write(chunk)
                            downloaded += len(chunk)
                            if total > 0:
                                self._update_local_task(
                                    task_id,
                                    progress=min(99, int(downloaded * 100 / total)),
                                    status=f"{downloaded}/{total} bytes",
                                )
            self._update_local_task(task_id, state=2, status=f"saved to {target_path}", progress=100)
        except Exception as exc:
            if target_path.exists():
                target_path.unlink(missing_ok=True)
            self._update_local_task(task_id, state=-1, status="failed", error=str(exc), progress=0)

    def get_local_download_path(self, task_id: str) -> Path:
        with _LOCAL_DOWNLOAD_LOCK:
            task = _LOCAL_DOWNLOAD_TASKS.get(task_id)
            file_path = _LOCAL_DOWNLOAD_FILES.get(task_id)

        if task is None or file_path is None:
            raise ApiError(status_code=404, code="download_task_not_found", message="Download task was not found")
        if task.error:
            raise ApiError(status_code=409, code="download_failed", message=task.error)
        if task.progress < 100 and task.state != 2:
            raise ApiError(status_code=409, code="download_not_ready", message="Download task is not complete")

        allowed_dirs = [DOWNLOAD_DIR.resolve(), PICTURE_DIR.resolve()]
        resolved_path = file_path.resolve()
        if not any(resolved_path.is_relative_to(directory) for directory in allowed_dirs) or not resolved_path.is_file():
            raise ApiError(status_code=404, code="download_file_not_found", message="Downloaded file was not found")
        return resolved_path

    def get_existing_local_download_task(self, filename: str, *, download_dir: Path = DOWNLOAD_DIR) -> AListTask | None:
        file_path = download_dir / self._sanitize_filename(filename)
        if not file_path.is_file():
            return None
        task_id = self._local_file_task_id(file_path.name, download_dir=download_dir)
        task = AListTask(
            id=task_id,
            name=f"downloaded file {file_path.name} in ({download_dir})",
            state=2,
            status=f"saved to {file_path}",
            progress=100,
            error="",
        )
        with _LOCAL_DOWNLOAD_LOCK:
            _LOCAL_DOWNLOAD_TASKS[task_id] = task
            _LOCAL_DOWNLOAD_FILES[task_id] = file_path
        return task

    @staticmethod
    def _get_local_tasks(task_ids: list[str]) -> list[AListTask]:
        with _LOCAL_DOWNLOAD_LOCK:
            if task_ids:
                return [task for task_id in task_ids if (task := _LOCAL_DOWNLOAD_TASKS.get(task_id))]
            return list(_LOCAL_DOWNLOAD_TASKS.values())

    @staticmethod
    def _update_local_task(
        task_id: str,
        *,
        state: int | None = None,
        status: str | None = None,
        progress: int | None = None,
        error: str | None = None,
    ) -> None:
        with _LOCAL_DOWNLOAD_LOCK:
            task = _LOCAL_DOWNLOAD_TASKS.get(task_id)
            if task is None:
                return
            _LOCAL_DOWNLOAD_TASKS[task_id] = task.model_copy(
                update={
                    key: value
                    for key, value in {
                        "state": state,
                        "status": status,
                        "progress": progress,
                        "error": error,
                    }.items()
                    if value is not None
                }
            )

    @staticmethod
    def _download_filename(payload: AListOfflineDownloadRequest, source_path: str, download_url: str) -> str:
        if payload.name:
            return AListService._sanitize_filename(payload.name)
        if source_path:
            return AListService._sanitize_filename(Path(source_path).name)
        parsed_name = Path(unquote(urlparse(download_url).path)).name
        return AListService._sanitize_filename(parsed_name or f"download-{uuid4().hex}")

    @staticmethod
    def _sanitize_filename(filename: str) -> str:
        cleaned = "".join("_" if char in {"/", "\\", ":", "*", "?", '"', "<", ">", "|"} else char for char in filename)
        return cleaned.strip() or f"download-{uuid4().hex}"

    @staticmethod
    def _unique_download_path(path: Path) -> Path:
        if not path.exists():
            return path
        stem = path.stem
        suffix = path.suffix
        for index in range(1, 1000):
            candidate = path.with_name(f"{stem}-{index}{suffix}")
            if not candidate.exists():
                return candidate
        return path.with_name(f"{stem}-{uuid4().hex}{suffix}")

    @staticmethod
    def _local_file_task_id(filename: str, *, download_dir: Path = DOWNLOAD_DIR) -> str:
        return f"local-file-{uuid5(NAMESPACE_URL, f'{download_dir.name}/{filename}').hex}"

    @staticmethod
    def _local_download_dir(path: str) -> Path:
        return PICTURE_DIR if path.strip("/").split("/")[-1] == "picture" else DOWNLOAD_DIR

    def _post_file_list(self, client: httpx.Client, payload: AListFileListRequest) -> httpx.Response:
        response = self._post_with_auth(
            client,
            "/api/fs/list",
            json=payload.model_dump(),
        )
        if response.status_code not in {401, 403}:
            return response

        self._clear_token()
        return self._post_with_auth(
            client,
            "/api/fs/list",
            json=payload.model_dump(),
        )

    def _post_with_auth(
        self,
        client: httpx.Client,
        path: str,
        *,
        json: Any | None = None,
        params: dict[str, str] | None = None,
    ) -> httpx.Response:
        return client.post(path, json=json, params=params, headers={"Authorization": self._get_token(client)})

    def _get_token(self, client: httpx.Client) -> str:
        now = monotonic()
        cache_key = self._cache_key()
        with _TOKEN_CACHE_LOCK:
            cached = _TOKEN_CACHE.get(cache_key)
            if cached and now < cached[1]:
                self._token, self._token_expires_at = cached
                return self._token

        if not self._username or not self._password:
            raise ApiError(
                status_code=500,
                code="alist_not_configured",
                message="ALIST_USERNAME and ALIST_PASSWORD are required",
            )

        try:
            response = client.post(
                "/api/auth/login",
                json={"username": self._username, "password": self._password},
                headers={"Client-Id": self._client_id},
            )
            payload = response.json()
        except httpx.HTTPError as exc:
            raise ApiError(
                status_code=502,
                code="alist_auth_failed",
                message=f"Failed to authenticate with AList: {exc}",
            ) from exc
        except ValueError as exc:
            raise ApiError(
                status_code=502,
                code="alist_invalid_response",
                message="AList auth returned an invalid JSON response",
            ) from exc

        raw_response = AListRawResponse.model_validate(payload)
        token = payload.get("data", {}).get("token") if isinstance(payload.get("data"), dict) else None
        if response.status_code >= 400 or raw_response.code != 200 or not token:
            raise ApiError(
                status_code=502,
                code="alist_auth_failed",
                message=raw_response.message or "AList authentication failed",
            )

        self._token = str(token)
        self._token_expires_at = now + _TOKEN_TTL_SECONDS
        with _TOKEN_CACHE_LOCK:
            _TOKEN_CACHE[cache_key] = (self._token, self._token_expires_at)
        return self._token

    def _clear_token(self) -> None:
        self._token = None
        self._token_expires_at = 0.0
        with _TOKEN_CACHE_LOCK:
            _TOKEN_CACHE.pop(self._cache_key(), None)

    def _cache_key(self) -> str:
        return f"{self._base_url}|{self._username}|{self._client_id}"

    def _build_client(self) -> httpx.Client:
        return httpx.Client(base_url=self._base_url, timeout=self._timeout)

    def _parse_response(self, response: httpx.Response, response_model: type[Any], *, code: str) -> Any:
        try:
            raw_payload = response.json()
            raw_response = AListRawResponse.model_validate(raw_payload)
        except (ValueError, TypeError) as exc:
            raise ApiError(
                status_code=502,
                code="alist_invalid_response",
                message="AList returned an invalid JSON response",
            ) from exc

        if response.status_code >= 400 or raw_response.code != 200:
            if response.status_code in {401, 403} or self._is_auth_failure(raw_response):
                self._clear_token()
            raise ApiError(
                status_code=502,
                code=code,
                message=raw_response.message or f"AList request failed with status {response.status_code}",
            )

        try:
            return response_model.model_validate(raw_payload)
        except Exception as exc:
            raise ApiError(
                status_code=502,
                code="alist_invalid_response",
                message="AList response format does not match expected schema",
            ) from exc

    def _get_cached_file_list(self, payload: AListFileListRequest) -> AListFileListResponse | None:
        if payload.refresh:
            return None
        cache_key = self._file_list_cache_key(payload)
        now = monotonic()
        with _FILE_CACHE_LOCK:
            cached = _FILE_LIST_CACHE.get(cache_key)
            if cached and now < cached[1]:
                self._index_file_metadata(payload, cached[0])
                return cached[0]
        return None

    def _cache_file_list(self, payload: AListFileListRequest, response: AListFileListResponse) -> None:
        expires_at = monotonic() + _FILE_LIST_CACHE_TTL_SECONDS
        with _FILE_CACHE_LOCK:
            _FILE_LIST_CACHE[self._file_list_cache_key(payload)] = (response, expires_at)
            self._index_file_metadata(payload, response)

    def _index_file_metadata(self, payload: AListFileListRequest, response: AListFileListResponse) -> None:
        for item in response.data.content:
            full_path = self._full_file_path(payload.path, item)
            _FILE_META_CACHE[full_path] = item
            if item.path:
                _FILE_META_CACHE[item.path] = item

    @staticmethod
    def _file_list_cache_key(payload: AListFileListRequest) -> str:
        return f"{payload.path}|{payload.password}|{payload.page}|{payload.per_page}"

    def _build_cached_file_download_url(self, payload: AListOfflineDownloadRequest) -> str:
        source_path = payload.source_path or self._join_path(payload.list_path or "", payload.name or "")
        if not source_path:
            raise ApiError(
                status_code=422,
                code="alist_download_source_missing",
                message="Download source path is required",
            )

        item = self._resolve_cached_file_item(payload, source_path)
        if item is None:
            raise ApiError(
                status_code=404,
                code="alist_file_metadata_not_cached",
                message="File metadata is not cached and could not be refreshed. Refresh the file list before downloading.",
            )
        if item.is_dir:
            raise ApiError(
                status_code=422,
                code="alist_download_source_is_directory",
                message="Directories cannot be submitted as offline download URLs",
            )

        full_path = quote(source_path, safe="/")
        sign = f"?sign={quote(item.sign)}" if item.sign else ""
        return f"{self._base_url}/d{full_path}{sign}"

    def _resolve_cached_file_item(
        self,
        payload: AListOfflineDownloadRequest,
        source_path: str,
    ) -> AListFileItem | None:
        candidates = [source_path]
        if payload.list_path and payload.name:
            candidates.append(self._join_path(payload.list_path, payload.name))

        item = self._find_cached_file_item(candidates, payload.name)
        if item is not None:
            return item

        if payload.list_path:
            self.list_files(
                AListFileListRequest(
                    path=payload.list_path,
                    password="",
                    page=1,
                    per_page=100,
                    refresh=False,
                )
            )

        return self._find_cached_file_item(candidates, payload.name)

    def _find_cached_file_item(self, candidates: list[str], name: str | None) -> AListFileItem | None:
        with _FILE_CACHE_LOCK:
            for candidate in candidates:
                item = _FILE_META_CACHE.get(candidate)
                if item is not None:
                    return item
            if name:
                for cached_path, item in _FILE_META_CACHE.items():
                    if item.name == name and cached_path.endswith(f"/{name}"):
                        return item
        return None

    @staticmethod
    def _full_file_path(list_path: str, item: AListFileItem) -> str:
        if item.virtual_path and item.virtual_path.endswith(f"/{item.name}"):
            return item.virtual_path
        if item.path and item.path.endswith(f"/{item.name}"):
            return item.path
        return AListService._join_path(item.path or list_path, item.name)

    @staticmethod
    def _join_path(base_path: str, name: str) -> str:
        return f"{base_path.rstrip('/')}/{name.lstrip('/')}" if base_path else f"/{name.lstrip('/')}"

    def _get_task_info(self, client: httpx.Client, task_id: str) -> AListTask | None:
        response = self._post_with_auth(client, "/api/task/offline_download/info", params={"tid": task_id})
        if response.status_code >= 400:
            return None

        try:
            raw_payload = response.json()
            raw_response = AListRawResponse.model_validate(raw_payload)
            data = raw_response.data or {}
            task_payload = data.get("task") if isinstance(data, dict) else None
            return AListTask.model_validate(task_payload) if task_payload else None
        except Exception:
            return None

    def _list_tasks(self, client: httpx.Client, bucket: str) -> list[AListTask]:
        response = self._post_with_auth(client, f"/api/task/offline_download/{bucket}")
        if response.status_code >= 400:
            return []
        try:
            payload = response.json()
            data = payload.get("data")
            if isinstance(data, list):
                return [AListTask.model_validate(item) for item in data]
            if isinstance(data, dict) and isinstance(data.get("tasks"), list):
                return [AListTask.model_validate(item) for item in data["tasks"]]
            return []
        except Exception:
            return []

    def _find_task_in_buckets(self, client: httpx.Client, task_id: str) -> AListTask | None:
        for bucket in ("undone", "done"):
            for task in self._list_tasks(client, bucket):
                if task.id == task_id:
                    return task
        return None

    @staticmethod
    def _is_auth_failure(response: AListRawResponse) -> bool:
        message = response.message.lower()
        return response.code in {401, 403} or "token" in message or "auth" in message or "unauthorized" in message


def get_alist_service() -> AListService:
    return AListService()
