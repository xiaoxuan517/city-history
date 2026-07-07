from __future__ import annotations

import logging
from datetime import UTC, datetime
from time import monotonic, perf_counter

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.config.settings import settings
from app.db.models.gazetteer_file import GazetteerFile
from app.schemas.alist import AListFileListRequest, AListFileItem
from app.services.alist_service import AListService

logger = logging.getLogger(__name__)


class GazetteerFileService:
    def list_files(
        self,
        session: Session,
        *,
        q: str = "",
        page: int = 1,
        per_page: int = 10,
    ) -> tuple[list[GazetteerFile], int]:
        start = perf_counter()
        statement = select(GazetteerFile)
        count_statement = select(func.count()).select_from(GazetteerFile)
        keyword = q.strip()
        if keyword:
            pattern = f"%{keyword}%"
            condition = or_(GazetteerFile.name.ilike(pattern), GazetteerFile.full_path.ilike(pattern))
            statement = statement.where(condition)
            count_statement = count_statement.where(condition)

        total = int(session.scalar(count_statement) or 0)
        rows = list(
            session.scalars(
                statement.order_by(GazetteerFile.full_path.asc())
                .offset((page - 1) * per_page)
                .limit(per_page)
            )
        )
        logger.info(
            "县志文件分页查询完成。q=%s page=%s per_page=%s total=%s rows=%s elapsed_ms=%.2f",
            keyword,
            page,
            per_page,
            total,
            len(rows),
            (perf_counter() - start) * 1000,
        )
        return rows, total

    def sync_from_alist(
        self,
        session: Session,
        *,
        root_path: str = settings.gazetteer_file_root_path,
        alist_service: AListService | None = None,
    ) -> int:
        service = alist_service or AListService(timeout=60.0)
        root_request_path = root_path.rstrip("/") or "/"
        queue = [root_request_path]
        seen_dirs: set[str] = set()
        synced_at = datetime.now(UTC)
        synced_count = 0
        visited_dir_count = 0

        logger.info("县志文件同步开始。root_path=%s", root_request_path)

        while queue:
            current_request_path = queue.pop(0)
            if current_request_path in seen_dirs:
                continue
            seen_dirs.add(current_request_path)
            visited_dir_count += 1
            logger.info(
                "扫描县志目录。dir=%s remaining_dirs=%s visited_dirs=%s",
                current_request_path,
                len(queue),
                visited_dir_count,
            )

            page = 1
            while True:
                try:
                    response = service.list_files(
                        AListFileListRequest(
                            path=current_request_path,
                            password="",
                            page=page,
                            per_page=200,
                            refresh=False,
                        )
                    )
                except Exception:
                    logger.exception("扫描县志目录失败。dir=%s page=%s", current_request_path, page)
                    break

                items = response.data.content
                page_dir_count = 0
                page_file_count = 0
                for item in items:
                    request_path = _request_child_path(current_request_path, item.name)
                    full_path = _display_full_path(current_request_path, item)
                    if item.is_dir:
                        queue.append(request_path)
                        page_dir_count += 1
                        logger.debug(
                            "县志目录入队。parent=%s name=%s request_path=%s display_path=%s",
                            current_request_path,
                            item.name,
                            request_path,
                            full_path,
                        )
                        continue
                    self._upsert_file(session, item=item, full_path=full_path, synced_at=synced_at)
                    synced_count += 1
                    page_file_count += 1

                session.commit()
                logger.info(
                    "扫描县志目录分页完成。dir=%s page=%s total=%s items=%s dirs=%s files=%s synced_files=%s queue=%s",
                    current_request_path,
                    page,
                    response.data.total,
                    len(items),
                    page_dir_count,
                    page_file_count,
                    synced_count,
                    len(queue),
                )
                if len(items) < 200 or page * 200 >= response.data.total:
                    break
                page += 1

        logger.info("县志文件同步结束。visited_dirs=%s synced_files=%s", visited_dir_count, synced_count)
        return synced_count

    def _upsert_file(self, session: Session, *, item: AListFileItem, full_path: str, synced_at: datetime) -> None:
        existing = session.scalar(select(GazetteerFile).where(GazetteerFile.full_path == full_path))
        if existing is None:
            session.add(
                GazetteerFile(
                    name=item.name,
                    full_path=full_path,
                    size=item.size,
                    modified=item.modified,
                    synced_at=synced_at,
                )
            )
            return

        existing.name = item.name
        existing.size = item.size
        existing.modified = item.modified
        existing.synced_at = synced_at


class GazetteerFileSyncState:
    running = False
    last_started_at: datetime | None = None
    last_finished_at: datetime | None = None
    last_error: str | None = None
    last_synced_count = 0
    last_duration_seconds = 0.0


def sync_gazetteer_files_once() -> int:
    if GazetteerFileSyncState.running:
        return 0

    from app.db.session import get_session_factory

    GazetteerFileSyncState.running = True
    GazetteerFileSyncState.last_started_at = datetime.now(UTC)
    start = monotonic()
    try:
        with get_session_factory()() as session:
            count = GazetteerFileService().sync_from_alist(session)
        GazetteerFileSyncState.last_synced_count = count
        GazetteerFileSyncState.last_error = None
        return count
    except Exception as exc:
        GazetteerFileSyncState.last_error = str(exc)
        raise
    finally:
        GazetteerFileSyncState.last_duration_seconds = monotonic() - start
        GazetteerFileSyncState.last_finished_at = datetime.now(UTC)
        GazetteerFileSyncState.running = False


def get_gazetteer_file_service() -> GazetteerFileService:
    return GazetteerFileService()


def source_path_for_display_path(full_path: str, *, root_path: str = settings.gazetteer_file_root_path) -> str:
    if full_path.startswith(root_path):
        return full_path
    root_parts = [part for part in root_path.split("/") if part]
    if len(root_parts) >= 2 and full_path.startswith(f"/{root_parts[1]}"):
        return f"/{root_parts[0]}{full_path}"
    return full_path


def _request_child_path(parent_request_path: str, name: str) -> str:
    return f"{parent_request_path.rstrip('/')}/{name.lstrip('/')}" if parent_request_path else f"/{name.lstrip('/')}"


def _display_full_path(list_path: str, item: AListFileItem) -> str:
    if item.path and item.path.endswith(f"/{item.name}"):
        return item.path
    base_path = item.path or list_path
    return f"{base_path.rstrip('/')}/{item.name.lstrip('/')}" if base_path else f"/{item.name.lstrip('/')}"
