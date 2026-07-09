from __future__ import annotations

import mimetypes
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.errors import ApiError
from app.db.session import get_db_session
from app.schemas.old_picture import LocalOldPictureListResponse, LocalOldPictureRead, OldPictureListResponse, OldPictureRead
from app.services.alist_service import AListService, PICTURE_DIR, PREVIEW_DIR, get_alist_service
from app.services.old_picture_service import (
    OldPictureService,
    get_old_picture_service,
    old_picture_source_path_for_display_path,
)

router = APIRouter(prefix="/api/v1/old-pictures", tags=["old_pictures"])


@router.get("", response_model=OldPictureListResponse)
def list_old_pictures(
    q: str = Query(default=""),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=12, ge=1, le=200),
    session: Session = Depends(get_db_session),
    old_picture_service: OldPictureService = Depends(get_old_picture_service),
    alist_service: AListService = Depends(get_alist_service),
) -> OldPictureListResponse:
    rows, total = old_picture_service.list_pictures(session, q=q, page=page, per_page=per_page)
    return OldPictureListResponse(
        items=[_to_old_picture_read(row, alist_service) for row in rows],
        total=total,
        page=page,
        per_page=per_page,
    )


@router.get("/local", response_model=LocalOldPictureListResponse)
def list_local_old_pictures(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=50),
    old_picture_service: OldPictureService = Depends(get_old_picture_service),
    alist_service: AListService = Depends(get_alist_service),
) -> LocalOldPictureListResponse:
    files, total = old_picture_service.list_local_pictures(offset=offset, limit=limit)
    items: list[LocalOldPictureRead] = []
    for picture in files:
        task = alist_service.get_existing_local_download_task(picture.original_path.name, download_dir=PICTURE_DIR)
        if task is None:
            continue
        stat = picture.original_path.stat()
        items.append(
            LocalOldPictureRead(
                name=picture.original_path.name,
                preview_name=picture.preview_path.name,
                size=stat.st_size,
                modified=datetime.fromtimestamp(stat.st_mtime, UTC),
                local_download_task_id=task.id,
            )
        )
    return LocalOldPictureListResponse(items=items, total=total, offset=offset, limit=limit)


@router.get("/local-preview/{filename}")
def preview_local_old_picture(filename: str) -> FileResponse:
    file_path = (PREVIEW_DIR / filename).resolve()
    preview_dir = PREVIEW_DIR.resolve()
    if not file_path.is_relative_to(preview_dir) or not file_path.is_file():
        raise ApiError(status_code=404, code="old_picture_preview_not_found", message="Preview image was not found")
    media_type = mimetypes.guess_type(file_path.name)[0] or "image/webp"
    return FileResponse(
        path=file_path,
        filename=file_path.name,
        media_type=media_type,
        content_disposition_type="inline",
        headers={"Cache-Control": "public, max-age=86400"},
    )


def _to_old_picture_read(row, alist_service: AListService) -> OldPictureRead:
    local_task = alist_service.get_existing_local_download_task(row.name, download_dir=PICTURE_DIR)
    return OldPictureRead(
        id=row.id,
        name=row.name,
        full_path=row.full_path,
        source_path=old_picture_source_path_for_display_path(row.full_path),
        is_downloaded=local_task is not None,
        local_download_task_id=local_task.id if local_task else None,
        size=row.size,
        modified=row.modified,
        synced_at=row.synced_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )
