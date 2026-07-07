from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any


class RuntimeRunStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class DisconnectMode(StrEnum):
    CANCEL = "cancel"
    CONTINUE = "continue"


@dataclass
class RuntimeRun:
    run_id: int
    session_id: int
    user_id: int
    kb_id: int
    status: RuntimeRunStatus = RuntimeRunStatus.PENDING
    task: asyncio.Task[Any] | None = None
    abort_event: asyncio.Event = field(default_factory=asyncio.Event)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    error: str | None = None


@dataclass(frozen=True)
class StreamEvent:
    id: int
    event: str
    data: Any
