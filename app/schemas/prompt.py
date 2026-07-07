from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class PromptVersionCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    version: str = Field(..., min_length=1, max_length=64)
    description: str | None = Field(default=None, max_length=4000)
    system_prompt: str = Field(..., min_length=1)


class PromptVersionRead(BaseModel):
    id: int
    name: str
    version: str
    description: str | None
    system_prompt: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
