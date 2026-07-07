from __future__ import annotations

import json
import threading
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from app.config.settings import settings

FeedbackRating = Literal["up", "down"]


@dataclass(frozen=True)
class FeedbackRecord:
    feedback_id: str
    created_at: str
    thread_id: str
    message_id: str
    rating: FeedbackRating
    question: str | None = None
    answer: str | None = None
    comment: str | None = None
    citations: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class FeedbackService:
    def __init__(self, log_path: str) -> None:
        self._log_path = Path(log_path)
        self._lock = threading.Lock()

    @property
    def log_path(self) -> Path:
        return self._log_path

    def record(
        self,
        *,
        thread_id: str,
        message_id: str,
        rating: FeedbackRating,
        question: str | None = None,
        answer: str | None = None,
        comment: str | None = None,
        citations: list[dict[str, Any]] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> FeedbackRecord:
        record = FeedbackRecord(
            feedback_id=uuid4().hex,
            created_at=datetime.now(UTC).isoformat(),
            thread_id=thread_id,
            message_id=message_id,
            rating=rating,
            question=question,
            answer=answer,
            comment=comment,
            citations=citations or [],
            metadata=metadata or {},
        )
        self._append(record)
        return record

    def _append(self, record: FeedbackRecord) -> None:
        self._log_path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(asdict(record), ensure_ascii=False, sort_keys=True)
        with self._lock:
            with self._log_path.open("a", encoding="utf-8") as file:
                file.write(f"{line}\n")


@lru_cache(maxsize=1)
def get_feedback_service() -> FeedbackService:
    return FeedbackService(settings.feedback_log_path)
