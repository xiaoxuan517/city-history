from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.db.models.chat import ChatRole, ChatRunStatus


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=8000)
    session_id: int | None = None


class RetrievalPreviewRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=8000)
    search_type: str | None = None
    top_k: int | None = Field(default=None, gt=0)
    fetch_k: int | None = Field(default=None, gt=0)
    reranker_enabled: bool | None = None


class RetrievalPreviewChunk(BaseModel):
    rank: int | None
    document_id: int | str | None
    filename: str
    chunk_id: int | str | None
    chunk_index: int | None
    page: str | None = None
    score: float | None = None
    content: str
    metadata: dict[str, Any]


class RetrievalPreviewResponse(BaseModel):
    question: str
    kb_id: int
    chunks: list[RetrievalPreviewChunk]


class ChatAnswerResponse(BaseModel):
    answer: str
    references: list[dict[str, Any]]
    session_id: int
    run_id: int
    usage: dict[str, Any] | None = None
    token_cost: dict[str, Any] | None = None


class ChatSessionRead(BaseModel):
    id: int
    user_id: int
    kb_id: int
    title: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ChatMessageRead(BaseModel):
    id: int
    session_id: int
    role: ChatRole
    content: str
    references: list[dict[str, Any]]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ChatRunRead(BaseModel):
    id: int
    session_id: int
    user_id: int
    kb_id: int
    prompt_version_id: int | None
    status: ChatRunStatus
    question: str
    answer: str | None
    references: list[dict[str, Any]]
    usage: dict[str, Any]
    token_cost: dict[str, Any]
    trace_id: str | None
    trace_url: str | None
    cache_hit: bool
    error_message: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ChatRunEventRead(BaseModel):
    id: int
    run_id: int
    user_id: int
    kb_id: int
    event_type: str
    sequence: int
    payload: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ChatRunCancelResponse(BaseModel):
    run_id: int
    cancelled: bool
