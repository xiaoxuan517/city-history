from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from app.retrieval.citations import Citation

RagStreamEventType = Literal["answer", "tool_call", "tool_result", "complete"]


@dataclass(frozen=True)
class RagResponse:
    thread_id: str
    answer: str
    status_lines: list[str] = field(default_factory=list)
    citations: list[Citation] = field(default_factory=list)
    usage: dict[str, Any] | None = None
    elapsed_ms: int | None = None


@dataclass(frozen=True)
class RagStreamEvent:
    type: RagStreamEventType
    content: str = ""
    answer: str = ""
    status_line: str | None = None
    tool_name: str | None = None
    citations: list[Citation] = field(default_factory=list)
    result: RagResponse | None = None
