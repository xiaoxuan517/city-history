from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class AssistantChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    state: dict[str, Any] = Field(default_factory=dict)
    session_id: int | None = None


class AssistantAction(BaseModel):
    type: str
    payload: dict[str, Any] = Field(default_factory=dict)


class AssistantChatResponse(BaseModel):
    answer: str
    actions: list[AssistantAction] = Field(default_factory=list)
    state: dict[str, Any] = Field(default_factory=dict)
    session_id: int | None = None
    run_id: int | None = None
