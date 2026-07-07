from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class GazetteerFileRead(BaseModel):
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


class GazetteerFileListResponse(BaseModel):
    items: list[GazetteerFileRead]
    total: int
    page: int
    per_page: int


class GazetteerFileListQuery(BaseModel):
    q: str = ""
    page: int = Field(default=1, ge=1)
    per_page: int = Field(default=10, ge=1, le=200)
