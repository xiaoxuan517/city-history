from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.db.models.document import DocumentStatus


class DocumentRead(BaseModel):
    id: int
    kb_id: int
    user_id: int
    filename: str
    content_type: str | None
    file_path: str
    status: DocumentStatus
    error_message: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DocumentProcessResponse(BaseModel):
    document: DocumentRead
    parsed_units: int
    chunk_count: int
