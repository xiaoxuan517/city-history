from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.schemas.gazetteer_file import GazetteerFileListResponse, GazetteerFileRead
from app.services.alist_service import AListService, get_alist_service
from app.services.gazetteer_file_service import (
    GazetteerFileService,
    get_gazetteer_file_service,
    source_path_for_display_path,
)

router = APIRouter(prefix="/api/v1/gazetteer-files", tags=["gazetteer_files"])


@router.get("", response_model=GazetteerFileListResponse)
def list_gazetteer_files(
    q: str = Query(default=""),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=10, ge=1, le=200),
    session: Session = Depends(get_db_session),
    gazetteer_file_service: GazetteerFileService = Depends(get_gazetteer_file_service),
    alist_service: AListService = Depends(get_alist_service),
) -> GazetteerFileListResponse:
    rows, total = gazetteer_file_service.list_files(session, q=q, page=page, per_page=per_page)
    return GazetteerFileListResponse(
        items=[
            _to_gazetteer_file_read(row, alist_service)
            for row in rows
        ],
        total=total,
        page=page,
        per_page=per_page,
    )


def _to_gazetteer_file_read(row, alist_service: AListService) -> GazetteerFileRead:
    local_task = alist_service.get_existing_local_download_task(row.name)
    return GazetteerFileRead(
        id=row.id,
        name=row.name,
        full_path=row.full_path,
        source_path=source_path_for_display_path(row.full_path),
        is_downloaded=local_task is not None,
        local_download_task_id=local_task.id if local_task else None,
        size=row.size,
        modified=row.modified,
        synced_at=row.synced_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )
