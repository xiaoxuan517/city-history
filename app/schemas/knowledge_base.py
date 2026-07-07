from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.document import DocumentRead


class KnowledgeBaseCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    description: str | None = Field(default=None, max_length=4000)


class KnowledgeBaseUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    description: str | None = Field(default=None, max_length=4000)


class KnowledgeBaseRead(BaseModel):
    id: int
    user_id: int
    name: str
    description: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class KnowledgeBaseFromDownloadRequest(BaseModel):
    task_id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1, max_length=128)
    description: str | None = Field(default=None, max_length=4000)


class KnowledgeBaseWithDocumentResponse(BaseModel):
    knowledge_base: KnowledgeBaseRead
    document: DocumentRead
