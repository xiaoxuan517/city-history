from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.schemas.old_picture import LocalOldPictureListResponse, LocalOldPictureRead, OldPictureListResponse, OldPictureRead
from app.services.alist_service import AListService, PICTURE_DIR, get_alist_service
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
    for path in files:
        task = alist_service.get_existing_local_download_task(path.name, download_dir=PICTURE_DIR)
        if task is None:
            continue
        stat = path.stat()
        items.append(
            LocalOldPictureRead(
                name=path.name,
                size=stat.st_size,
                modified=datetime.fromtimestamp(stat.st_mtime, UTC),
                local_download_task_id=task.id,
            )
        )
    return LocalOldPictureListResponse(items=items, total=total, offset=offset, limit=limit)


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
