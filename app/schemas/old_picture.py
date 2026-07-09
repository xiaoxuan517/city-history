from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class OldPictureRead(BaseModel):
    id: int
    name: str
    full_path: str
    source_path: str
    is_downloaded: bool = False
    local_download_task_id: str | None = None
    size: int
    modified: str
    synced_at: datetime
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class OldPictureListResponse(BaseModel):
    items: list[OldPictureRead]
    total: int
    page: int
    per_page: int


class LocalOldPictureRead(BaseModel):
    name: str
    preview_name: str
    size: int
    modified: datetime
    local_download_task_id: str


class LocalOldPictureListResponse(BaseModel):
    items: list[LocalOldPictureRead]
    total: int
    offset: int
    limit: int


class OldPictureListQuery(BaseModel):
    q: str = ""
    page: int = Field(default=1, ge=1)
    per_page: int = Field(default=12, ge=1, le=200)
