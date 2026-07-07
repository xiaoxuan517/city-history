from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterator, Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.chat import ChatMessage, ChatRole, ChatRun, ChatRunEvent, ChatRunStatus, ChatSession
from app.services.kb_service import KnowledgeBaseService
from app.services.prompt_version_service import PromptVersionService
from app.services.rag_service import RagService, get_rag_service
from app.services.token_cost import calculate_token_cost


class ChatSessionNotFoundError(ValueError):
    pass


@dataclass(frozen=True)
class ChatAnswer:
    answer: str
    references: list[dict[str, Any]]
    session_id: int
    run_id: int
    cache_hit: bool = False
    usage: dict[str, Any] | None = None
    token_cost: dict[str, Any] | None = None


@dataclass(frozen=True)
class PreparedChatRun:
    session_id: int
    run_id: int


@dataclass(frozen=True)
class ChatStreamEvent:
    type: Literal["answer_delta", "tool_call", "tool_result", "complete", "error"]
    content: str = ""
    answer: str = ""
    status_line: str | None = None
    tool_name: str | None = None
    citations: list[dict[str, Any]] | None = None
    result: ChatAnswer | None = None
    error_message: str | None = None


class ChatService:
    def __init__(
        self,
        *,
        kb_service: KnowledgeBaseService | None = None,
        rag_service: RagService | None = None,
        prompt_version_service: PromptVersionService | None = None,
    ) -> None:
        self._kb_service = kb_service or KnowledgeBaseService()
        self._rag_service = rag_service or get_rag_service()
        self._prompt_version_service = prompt_version_service or PromptVersionService()

    def prepare_run(
        self,
        session: Session,
        *,
        user_id: int,
        kb_id: int,
        question: str,
        session_id: int | None = None,
    ) -> PreparedChatRun:
        self._kb_service.get_for_user(session, user_id=user_id, kb_id=kb_id)
        chat_session = self._get_or_create_session(
            session,
            user_id=user_id,
            kb_id=kb_id,
            session_id=session_id,
            question=question,
        )
        user_message = ChatMessage(
            session_id=chat_session.id,
            role=ChatRole.USER,
            content=question,
            references=[],
        )
        session.add(user_message)
        session.commit()

        prompt_version = self._prompt_version_service.get_active(session)
        chat_run = self._create_run(
            session,
            user_id=user_id,
            kb_id=kb_id,
            chat_session_id=chat_session.id,
            question=question,
            prompt_version_id=prompt_version.id,
        )
        return PreparedChatRun(session_id=chat_session.id, run_id=chat_run.id)

    def run_prepared_stream(
        self,
        session: Session,
        *,
        user_id: int,
        kb_id: int,
        question: str,
        session_id: int,
        run_id: int,
    ) -> Iterator[ChatStreamEvent]:
        chat_run = self._get_run_for_user(session, user_id=user_id, run_id=run_id)
        prompt_version = (
            self._prompt_version_service.get_by_id(session, chat_run.prompt_version_id)
            if chat_run.prompt_version_id is not None
            else self._prompt_version_service.get_active(session)
        )
        event_sequence = 0
        try:
            answer = ""
            references: list[dict[str, Any]] = []
            usage: dict[str, Any] = _zero_usage(cached=False)
            cache_hit = False
            for event in self._rag_service.stream(
                question,
                thread_id=str(session_id),
                user_id=user_id,
                kb_id=kb_id,
                db_session=session,
                system_prompt=prompt_version.system_prompt,
            ):
                if event.type == "tool_call":
                    event_sequence += 1
                    self._record_run_event(
                        session,
                        chat_run=chat_run,
                        event_type="tool_call",
                        sequence=event_sequence,
                        payload={"status_line": event.status_line, "tool_name": event.tool_name},
                    )
                    yield ChatStreamEvent(
                        type="tool_call",
                        status_line=event.status_line,
                        tool_name=event.tool_name,
                    )
                    continue
                if event.type == "tool_result":
                    references = [dict(citation) for citation in event.citations]
                    event_sequence += 1
                    self._record_run_event(
                        session,
                        chat_run=chat_run,
                        event_type="tool_result",
                        sequence=event_sequence,
                        payload={
                            "status_line": event.status_line,
                            "tool_name": event.tool_name,
                            "content": event.content,
                            "citations": references,
                        },
                    )
                    yield ChatStreamEvent(
                        type="tool_result",
                        content=event.content,
                        status_line=event.status_line,
                        tool_name=event.tool_name,
                        citations=references,
                    )
                    continue
                if event.type == "answer":
                    answer = event.answer
                    yield ChatStreamEvent(type="answer_delta", content=event.content, answer=event.answer)
                    continue
                if event.type == "complete" and event.result is not None:
                    answer = event.result.answer
                    references = [dict(citation) for citation in event.result.citations]
                    usage = event.result.usage or usage

            assistant_message = ChatMessage(
                session_id=session_id,
                role=ChatRole.ASSISTANT,
                content=answer,
                references=references,
            )
            session.add(assistant_message)
            self._mark_run_completed(
                session,
                chat_run=chat_run,
                answer=answer,
                references=references,
                usage=usage,
                cache_hit=cache_hit,
            )
            event_sequence += 1
            self._record_run_event(
                session,
                chat_run=chat_run,
                event_type="complete",
                sequence=event_sequence,
                payload={
                    "answer_preview": answer[:500],
                    "reference_count": len(references),
                    "usage": usage,
                    "token_cost": calculate_token_cost(usage),
                    "cache_hit": cache_hit,
                },
            )
            session.commit()
            result = ChatAnswer(
                answer=answer,
                references=references,
                session_id=session_id,
                run_id=chat_run.id,
                cache_hit=cache_hit,
                usage=usage,
                token_cost=calculate_token_cost(usage),
            )
            yield ChatStreamEvent(type="complete", answer=answer, result=result)
        except Exception as exc:
            self._mark_run_failed(session, chat_run=chat_run, error_message=str(exc))
            event_sequence += 1
            self._record_run_event(
                session,
                chat_run=chat_run,
                event_type="error",
                sequence=event_sequence,
                payload={"message": str(exc)},
            )
            session.commit()
            yield ChatStreamEvent(type="error", error_message=str(exc))
            return

    def ask(
        self,
        session: Session,
        *,
        user_id: int,
        kb_id: int,
        question: str,
        session_id: int | None = None,
    ) -> ChatAnswer:
        self._kb_service.get_for_user(session, user_id=user_id, kb_id=kb_id)
        chat_session = self._get_or_create_session(
            session,
            user_id=user_id,
            kb_id=kb_id,
            session_id=session_id,
            question=question,
        )
        user_message = ChatMessage(
            session_id=chat_session.id,
            role=ChatRole.USER,
            content=question,
            references=[],
        )
        session.add(user_message)
        session.commit()

        prompt_version = self._prompt_version_service.get_active(session)
        chat_run = self._create_run(
            session,
            user_id=user_id,
            kb_id=kb_id,
            chat_session_id=chat_session.id,
            question=question,
            prompt_version_id=prompt_version.id,
        )
        try:
            answer_parts: list[str] = []
            references: list[dict[str, Any]] = []
            usage: dict[str, Any] = _zero_usage(cached=False)
            event_sequence = 0
            for event in self._rag_service.stream(
                question,
                thread_id=str(chat_session.id),
                user_id=user_id,
                kb_id=kb_id,
                db_session=session,
                system_prompt=prompt_version.system_prompt,
            ):
                if event.type == "answer":
                    answer_parts.append(event.content)
                elif event.type == "tool_call":
                    event_sequence += 1
                    self._record_run_event(
                        session,
                        chat_run=chat_run,
                        event_type="tool_call",
                        sequence=event_sequence,
                        payload={"status_line": event.status_line, "tool_name": event.tool_name},
                    )
                elif event.type == "tool_result":
                    references = [dict(citation) for citation in event.citations]
                    event_sequence += 1
                    self._record_run_event(
                        session,
                        chat_run=chat_run,
                        event_type="tool_result",
                        sequence=event_sequence,
                        payload={
                            "status_line": event.status_line,
                            "tool_name": event.tool_name,
                            "content": event.content,
                            "citations": references,
                        },
                    )
                elif event.type == "complete" and event.result is not None:
                    references = [dict(citation) for citation in event.result.citations]
                    usage = event.result.usage or usage
            answer = "".join(answer_parts)
            cache_hit = False
        except Exception as exc:
            self._mark_run_failed(session, chat_run=chat_run, error_message=str(exc))
            self._record_run_event(
                session,
                chat_run=chat_run,
                event_type="error",
                sequence=event_sequence + 1,
                payload={"message": str(exc)},
            )
            session.commit()
            raise

        assistant_message = ChatMessage(
            session_id=chat_session.id,
            role=ChatRole.ASSISTANT,
            content=answer,
            references=references,
        )
        session.add(assistant_message)
        self._mark_run_completed(
            session,
            chat_run=chat_run,
            answer=answer,
            references=references,
            usage=usage,
            cache_hit=cache_hit,
        )
        self._record_run_event(
            session,
            chat_run=chat_run,
            event_type="complete",
            sequence=event_sequence + 1,
            payload={
                "answer_preview": answer[:500],
                "reference_count": len(references),
                "usage": usage,
                "token_cost": calculate_token_cost(usage),
                "cache_hit": cache_hit,
            },
        )
        session.commit()
        return ChatAnswer(
            answer=answer,
            references=references,
            session_id=chat_session.id,
            run_id=chat_run.id,
            cache_hit=cache_hit,
            usage=usage,
            token_cost=calculate_token_cost(usage),
        )

    def stream(
        self,
        session: Session,
        *,
        user_id: int,
        kb_id: int,
        question: str,
        session_id: int | None = None,
    ) -> Iterator[ChatStreamEvent]:
        prepared = self.prepare_run(
            session,
            user_id=user_id,
            kb_id=kb_id,
            question=question,
            session_id=session_id,
        )
        yield from self.run_prepared_stream(
            session,
            user_id=user_id,
            kb_id=kb_id,
            question=question,
            session_id=prepared.session_id,
            run_id=prepared.run_id,
        )

    def _create_run(
        self,
        session: Session,
        *,
        user_id: int,
        kb_id: int,
        chat_session_id: int,
        question: str,
        prompt_version_id: int | None,
    ) -> ChatRun:
        chat_run = ChatRun(
            session_id=chat_session_id,
            user_id=user_id,
            kb_id=kb_id,
            prompt_version_id=prompt_version_id,
            status=ChatRunStatus.RUNNING,
            question=question,
            references=[],
            usage={},
            token_cost={},
            cache_hit=False,
        )
        session.add(chat_run)
        session.commit()
        session.refresh(chat_run)
        return chat_run

    def _mark_run_completed(
        self,
        session: Session,
        *,
        chat_run: ChatRun,
        answer: str,
        references: list[dict[str, Any]],
        usage: dict[str, Any],
        cache_hit: bool,
    ) -> None:
        chat_run.status = ChatRunStatus.COMPLETED
        chat_run.answer = answer
        chat_run.references = references
        chat_run.usage = usage
        chat_run.token_cost = calculate_token_cost(usage)
        chat_run.cache_hit = cache_hit
        chat_run.error_message = None

    def _mark_run_failed(self, session: Session, *, chat_run: ChatRun, error_message: str) -> None:
        chat_run.status = ChatRunStatus.FAILED
        chat_run.error_message = error_message
        session.commit()

    def list_sessions(self, session: Session, *, user_id: int) -> list[ChatSession]:
        statement = select(ChatSession).where(ChatSession.user_id == user_id).order_by(ChatSession.updated_at.desc())
        return list(session.scalars(statement))

    def list_messages(self, session: Session, *, user_id: int, session_id: int) -> list[ChatMessage]:
        chat_session = self._get_session_for_user(session, user_id=user_id, session_id=session_id)
        statement = select(ChatMessage).where(ChatMessage.session_id == chat_session.id).order_by(ChatMessage.created_at)
        return list(session.scalars(statement))

    def delete_session(self, session: Session, *, user_id: int, session_id: int) -> None:
        chat_session = self._get_session_for_user(session, user_id=user_id, session_id=session_id)
        session.delete(chat_session)
        session.commit()

    def list_run_events(self, session: Session, *, user_id: int, run_id: int) -> list[ChatRunEvent]:
        self._get_run_for_user(session, user_id=user_id, run_id=run_id)
        statement = (
            select(ChatRunEvent)
            .where(ChatRunEvent.run_id == run_id, ChatRunEvent.user_id == user_id)
            .order_by(ChatRunEvent.sequence, ChatRunEvent.id)
        )
        return list(session.scalars(statement))

    def _record_run_event(
        self,
        session: Session,
        *,
        chat_run: ChatRun,
        event_type: str,
        sequence: int,
        payload: dict[str, Any],
    ) -> None:
        session.add(
            ChatRunEvent(
                run_id=chat_run.id,
                user_id=chat_run.user_id,
                kb_id=chat_run.kb_id,
                event_type=event_type,
                sequence=sequence,
                payload=payload,
            )
        )

    def _get_or_create_session(
        self,
        session: Session,
        *,
        user_id: int,
        kb_id: int,
        session_id: int | None,
        question: str,
    ) -> ChatSession:
        if session_id is not None:
            chat_session = self._get_session_for_user(session, user_id=user_id, session_id=session_id)
            if chat_session.kb_id != kb_id:
                raise ChatSessionNotFoundError("Chat session not found")
            return chat_session

        title = question.strip()[:60] or "新会话"
        chat_session = ChatSession(user_id=user_id, kb_id=kb_id, title=title)
        session.add(chat_session)
        session.commit()
        session.refresh(chat_session)
        return chat_session

    def _get_session_for_user(self, session: Session, *, user_id: int, session_id: int) -> ChatSession:
        statement = select(ChatSession).where(ChatSession.id == session_id, ChatSession.user_id == user_id)
        chat_session = session.scalar(statement)
        if chat_session is None:
            raise ChatSessionNotFoundError("Chat session not found")
        return chat_session

    def _get_run_for_user(self, session: Session, *, user_id: int, run_id: int) -> ChatRun:
        statement = select(ChatRun).where(ChatRun.id == run_id, ChatRun.user_id == user_id)
        chat_run = session.scalar(statement)
        if chat_run is None:
            raise ChatSessionNotFoundError("Chat run not found")
        return chat_run

def _zero_usage(*, cached: bool) -> dict[str, Any]:
    return {
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "cached": cached,
    }


def get_chat_service() -> ChatService:
    return ChatService()
