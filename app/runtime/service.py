from __future__ import annotations

import asyncio
from functools import lru_cache
from typing import Any

from sqlalchemy.orm import Session

from app.db.models.chat import ChatRun, ChatRunStatus
from app.db.session import get_session_factory
from app.runtime.manager import RunManager, get_run_manager
from app.runtime.schemas import DisconnectMode, RuntimeRun, RuntimeRunStatus, StreamEvent
from app.runtime.serialization import serialize
from app.runtime.stream import MemoryStreamBridge, get_stream_bridge
from app.services.chat_service import ChatService, get_chat_service


class RuntimeService:
    def __init__(
        self,
        *,
        run_manager: RunManager | None = None,
        stream_bridge: MemoryStreamBridge | None = None,
        chat_service: ChatService | None = None,
    ) -> None:
        self._run_manager = run_manager or get_run_manager()
        self._stream_bridge = stream_bridge or get_stream_bridge()
        self._chat_service = chat_service or get_chat_service()

    async def start_chat_run(
        self,
        db: Session,
        *,
        user_id: int,
        kb_id: int,
        question: str,
        session_id: int | None,
    ) -> RuntimeRun:
        prepared = self._chat_service.prepare_run(
            db,
            user_id=user_id,
            kb_id=kb_id,
            question=question,
            session_id=session_id,
        )
        record = RuntimeRun(
            run_id=prepared.run_id,
            session_id=prepared.session_id,
            user_id=user_id,
            kb_id=kb_id,
        )
        await self._stream_bridge.ensure_run(record.run_id)
        active = self._run_manager.active_for_session(record.session_id)
        if active is not None and active.user_id == user_id:
            self._mark_db_run_cancelled(run_id=active.run_id, user_id=user_id)
        await self._run_manager.create_or_interrupt(record)

        loop = asyncio.get_running_loop()
        task = asyncio.create_task(
            asyncio.to_thread(
                self._run_chat_worker,
                loop,
                record,
                question,
            )
        )
        record.task = task
        return record

    async def stream_run(
        self,
        run_id: int,
        *,
        disconnect_mode: DisconnectMode = DisconnectMode.CANCEL,
    ):
        try:
            async for event in self._stream_bridge.subscribe(run_id):
                yield event
        finally:
            record = self._run_manager.get(run_id)
            if record is not None and record.status in {RuntimeRunStatus.PENDING, RuntimeRunStatus.RUNNING}:
                if disconnect_mode == DisconnectMode.CANCEL:
                    await self.cancel_run(run_id, user_id=record.user_id)

    async def cancel_run(self, run_id: int, *, user_id: int) -> bool:
        record = self._run_manager.get(run_id)
        if record is None or record.user_id != user_id:
            return False
        cancelled = await self._run_manager.cancel(run_id)
        if cancelled:
            self._mark_db_run_cancelled(run_id=run_id, user_id=user_id)
            await self._stream_bridge.publish(run_id, "error", {"message": "Run cancelled"})
            await self._stream_bridge.publish_end(run_id)
        return cancelled

    def get_run_for_user(self, db: Session, *, run_id: int, user_id: int) -> ChatRun | None:
        return db.get(ChatRun, run_id) if self._run_belongs_to_user(db, run_id=run_id, user_id=user_id) else None

    def _run_chat_worker(
        self,
        loop: asyncio.AbstractEventLoop,
        record: RuntimeRun,
        question: str,
    ) -> None:
        session = get_session_factory()()
        try:
            self._set_status_threadsafe(loop, record.run_id, RuntimeRunStatus.RUNNING)
            for event in self._chat_service.run_prepared_stream(
                session,
                user_id=record.user_id,
                kb_id=record.kb_id,
                question=question,
                session_id=record.session_id,
                run_id=record.run_id,
            ):
                if record.abort_event.is_set():
                    self._mark_db_run_cancelled(run_id=record.run_id, user_id=record.user_id)
                    self._set_status_threadsafe(loop, record.run_id, RuntimeRunStatus.CANCELLED)
                    self._stream_bridge.publish_threadsafe(
                        loop,
                        record.run_id,
                        "error",
                        {"message": "Run cancelled"},
                    )
                    return

                payload = _event_payload(event)
                self._stream_bridge.publish_threadsafe(loop, record.run_id, _event_name(event.type), payload)
                if event.type == "error":
                    self._set_status_threadsafe(
                        loop,
                        record.run_id,
                        RuntimeRunStatus.FAILED,
                        error=event.error_message,
                    )
                    return

            self._set_status_threadsafe(loop, record.run_id, RuntimeRunStatus.COMPLETED)
        except BaseException as exc:
            if isinstance(exc, asyncio.CancelledError):
                self._mark_db_run_cancelled(run_id=record.run_id, user_id=record.user_id)
                self._set_status_threadsafe(loop, record.run_id, RuntimeRunStatus.CANCELLED)
                self._stream_bridge.publish_threadsafe(
                    loop,
                    record.run_id,
                    "error",
                    {"message": "Run cancelled"},
                )
                return

            self._mark_db_run_failed(run_id=record.run_id, user_id=record.user_id, error_message=str(exc))
            self._set_status_threadsafe(loop, record.run_id, RuntimeRunStatus.FAILED, error=str(exc))
            self._stream_bridge.publish_threadsafe(loop, record.run_id, "error", {"message": str(exc)})
        finally:
            session.close()
            self._stream_bridge.publish_end_threadsafe(loop, record.run_id)
            asyncio.run_coroutine_threadsafe(self._run_manager.cleanup(record.run_id, delay=300), loop)
            asyncio.run_coroutine_threadsafe(self._stream_bridge.cleanup(record.run_id, delay=300), loop)

    def _set_status_threadsafe(
        self,
        loop: asyncio.AbstractEventLoop,
        run_id: int,
        status: RuntimeRunStatus,
        *,
        error: str | None = None,
    ) -> None:
        future = asyncio.run_coroutine_threadsafe(
            self._run_manager.set_status(run_id, status, error=error),
            loop,
        )
        future.result()

    def _run_belongs_to_user(self, db: Session, *, run_id: int, user_id: int) -> bool:
        run = db.get(ChatRun, run_id)
        return run is not None and run.user_id == user_id

    def _mark_db_run_cancelled(self, *, run_id: int, user_id: int) -> None:
        session = get_session_factory()()
        try:
            run = session.get(ChatRun, run_id)
            if run is not None and run.user_id == user_id:
                run.status = ChatRunStatus.CANCELLED
                run.error_message = "Run cancelled"
                session.commit()
        finally:
            session.close()

    def _mark_db_run_failed(self, *, run_id: int, user_id: int, error_message: str) -> None:
        session = get_session_factory()()
        try:
            run = session.get(ChatRun, run_id)
            if run is not None and run.user_id == user_id:
                run.status = ChatRunStatus.FAILED
                run.error_message = error_message
                session.commit()
        finally:
            session.close()


def _event_name(event_type: str) -> str:
    return "answer_delta" if event_type == "answer_delta" else event_type


def _event_payload(event: Any) -> dict[str, Any]:
    if event.type == "answer_delta":
        return {"content": event.content, "answer": event.answer}
    if event.type == "tool_call":
        return {"status_line": event.status_line, "tool_name": event.tool_name}
    if event.type == "tool_result":
        return {
            "status_line": event.status_line,
            "tool_name": event.tool_name,
            "content": event.content,
            "citations": serialize(event.citations or []),
        }
    if event.type == "complete" and event.result is not None:
        answer = event.result
        return {
            "answer": answer.answer,
            "references": serialize(answer.references),
            "session_id": answer.session_id,
            "run_id": answer.run_id,
            "cache_hit": answer.cache_hit,
            "usage": serialize(answer.usage),
            "token_cost": serialize(answer.token_cost),
        }
    if event.type == "error":
        return {"message": event.error_message or "chat stream failed"}
    return {}


@lru_cache(maxsize=1)
def get_runtime_service() -> RuntimeService:
    return RuntimeService()
