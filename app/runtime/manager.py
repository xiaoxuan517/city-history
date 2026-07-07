from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from app.runtime.schemas import RuntimeRun, RuntimeRunStatus

_ACTIVE_STATUSES = {
    RuntimeRunStatus.PENDING,
    RuntimeRunStatus.RUNNING,
}


class RunManager:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._runs: dict[int, RuntimeRun] = {}
        self._active_by_session: dict[int, int] = {}

    async def create_or_interrupt(self, record: RuntimeRun) -> RuntimeRun:
        async with self._lock:
            active_run_id = self._active_by_session.get(record.session_id)
            if active_run_id is not None:
                active = self._runs.get(active_run_id)
                if active is not None and active.status in _ACTIVE_STATUSES:
                    active.abort_event.set()
                    if active.task is not None:
                        active.task.cancel()
                    active.status = RuntimeRunStatus.CANCELLED
                    active.updated_at = datetime.now(timezone.utc)

            self._runs[record.run_id] = record
            self._active_by_session[record.session_id] = record.run_id
            return record

    def get(self, run_id: int) -> RuntimeRun | None:
        return self._runs.get(run_id)

    def active_for_session(self, session_id: int) -> RuntimeRun | None:
        run_id = self._active_by_session.get(session_id)
        return self._runs.get(run_id) if run_id is not None else None

    async def set_status(
        self,
        run_id: int,
        status: RuntimeRunStatus,
        *,
        error: str | None = None,
    ) -> None:
        async with self._lock:
            record = self._runs.get(run_id)
            if record is None:
                return

            record.status = status
            record.error = error
            record.updated_at = datetime.now(timezone.utc)
            if status not in _ACTIVE_STATUSES and self._active_by_session.get(record.session_id) == run_id:
                self._active_by_session.pop(record.session_id, None)

    async def cancel(self, run_id: int) -> bool:
        async with self._lock:
            record = self._runs.get(run_id)
            if record is None or record.status not in _ACTIVE_STATUSES:
                return False

            record.abort_event.set()
            if record.task is not None:
                record.task.cancel()
            record.status = RuntimeRunStatus.CANCELLED
            record.updated_at = datetime.now(timezone.utc)
            if self._active_by_session.get(record.session_id) == run_id:
                self._active_by_session.pop(record.session_id, None)
            return True

    async def cleanup(self, run_id: int, *, delay: float = 300) -> None:
        if delay > 0:
            await asyncio.sleep(delay)
        async with self._lock:
            record = self._runs.get(run_id)
            if record is None or record.status in _ACTIVE_STATUSES:
                return
            self._runs.pop(run_id, None)
            if self._active_by_session.get(record.session_id) == run_id:
                self._active_by_session.pop(record.session_id, None)


_run_manager = RunManager()


def get_run_manager() -> RunManager:
    return _run_manager
