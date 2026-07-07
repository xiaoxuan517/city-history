from __future__ import annotations

import threading
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from functools import lru_cache

from app.services.feedback_service import FeedbackRating


@dataclass(frozen=True)
class MetricsSnapshot:
    started_at: str
    uptime_seconds: int
    chat_requests_total: int
    chat_stream_requests_total: int
    chat_errors_total: int
    feedback_total: int
    feedback_up_total: int
    feedback_down_total: int
    average_chat_elapsed_ms: float | None
    last_chat_elapsed_ms: int | None


class MetricsService:
    def __init__(self) -> None:
        self._started_at = datetime.now(UTC)
        self._lock = threading.Lock()
        self._chat_requests_total = 0
        self._chat_stream_requests_total = 0
        self._chat_errors_total = 0
        self._feedback_up_total = 0
        self._feedback_down_total = 0
        self._chat_elapsed_count = 0
        self._chat_elapsed_sum_ms = 0
        self._last_chat_elapsed_ms: int | None = None

    def record_chat(self, *, elapsed_ms: int | None, stream: bool = False) -> None:
        with self._lock:
            if stream:
                self._chat_stream_requests_total += 1
            else:
                self._chat_requests_total += 1

            if elapsed_ms is not None:
                self._chat_elapsed_count += 1
                self._chat_elapsed_sum_ms += elapsed_ms
                self._last_chat_elapsed_ms = elapsed_ms

    def record_chat_error(self) -> None:
        with self._lock:
            self._chat_errors_total += 1

    def record_feedback(self, rating: FeedbackRating) -> None:
        with self._lock:
            if rating == "up":
                self._feedback_up_total += 1
            if rating == "down":
                self._feedback_down_total += 1

    def snapshot(self) -> MetricsSnapshot:
        with self._lock:
            average_elapsed = (
                self._chat_elapsed_sum_ms / self._chat_elapsed_count if self._chat_elapsed_count else None
            )
            feedback_total = self._feedback_up_total + self._feedback_down_total
            return MetricsSnapshot(
                started_at=self._started_at.isoformat(),
                uptime_seconds=int((datetime.now(UTC) - self._started_at).total_seconds()),
                chat_requests_total=self._chat_requests_total,
                chat_stream_requests_total=self._chat_stream_requests_total,
                chat_errors_total=self._chat_errors_total,
                feedback_total=feedback_total,
                feedback_up_total=self._feedback_up_total,
                feedback_down_total=self._feedback_down_total,
                average_chat_elapsed_ms=average_elapsed,
                last_chat_elapsed_ms=self._last_chat_elapsed_ms,
            )

    def snapshot_dict(self) -> dict[str, object]:
        return asdict(self.snapshot())


@lru_cache(maxsize=1)
def get_metrics_service() -> MetricsService:
    return MetricsService()
