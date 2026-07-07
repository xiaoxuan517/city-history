from __future__ import annotations

import mimetypes

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse

from app.schemas.alist import (
    AListFileListRequest,
    AListFileListResponse,
    AListOfflineDownloadRequest,
    AListOfflineDownloadResponse,
    AListTaskListRequest,
    AListTaskListResponse,
)
from app.services.alist_service import AListService, get_alist_service

router = APIRouter(prefix="/api/fs", tags=["fs"])


@router.post("/list", response_model=AListFileListResponse)
def list_files(
    payload: AListFileListRequest,
    alist_service: AListService = Depends(get_alist_service),
) -> AListFileListResponse:
    return alist_service.list_files(payload)


@router.post("/add_offline_download", response_model=AListOfflineDownloadResponse)
def add_offline_download(
    payload: AListOfflineDownloadRequest,
    alist_service: AListService = Depends(get_alist_service),
) -> AListOfflineDownloadResponse:
    return alist_service.add_offline_download(payload)


@router.post("/offline_download/tasks", response_model=AListTaskListResponse)
def list_offline_download_tasks(
    payload: AListTaskListRequest,
    alist_service: AListService = Depends(get_alist_service),
) -> AListTaskListResponse:
    return alist_service.list_offline_download_tasks(payload)


@router.get("/offline_download/tasks/{task_id}/file")
def download_local_task_file(
    task_id: str,
    alist_service: AListService = Depends(get_alist_service),
) -> FileResponse:
    file_path = alist_service.get_local_download_path(task_id)
    return FileResponse(path=file_path, filename=file_path.name, media_type="application/octet-stream")


@router.get("/offline_download/tasks/{task_id}/preview")
def preview_local_task_file(
    task_id: str,
    alist_service: AListService = Depends(get_alist_service),
) -> FileResponse:
    file_path = alist_service.get_local_download_path(task_id)
    media_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
    return FileResponse(
        path=file_path,
        filename=file_path.name,
        media_type=media_type,
        content_disposition_type="inline",
    )
