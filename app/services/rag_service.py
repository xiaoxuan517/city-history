from __future__ import annotations

import time
from functools import lru_cache
from typing import Any, Generator

from sqlalchemy.orm import Session

from app.retrieval.citations import Citation, citation_key
from app.retrieval.profile import RetrievalProfile
from app.services.chat_client import get_chat_client, new_thread_id
from app.services.rag_types import RagResponse, RagStreamEvent


class RagService:
    def __init__(self) -> None:
        self._client = get_chat_client()

    @property
    def agent(self):
        return self._client.agent

    def ask(
        self,
        user_input: str,
        *,
        thread_id: str | None = None,
        retrieval_profile: RetrievalProfile | None = None,
        user_id: int | None = None,
        kb_id: int | None = None,
        db_session: Session | None = None,
        system_prompt: str | None = None,
    ) -> RagResponse:
        resolved_thread_id = thread_id or new_thread_id()
        result = self._client.ask(
            user_input,
            resolved_thread_id,
            retrieval_profile=retrieval_profile,
            user_id=user_id,
            kb_id=kb_id,
            db_session=db_session,
            system_prompt=system_prompt,
        )
        return RagResponse(
            thread_id=resolved_thread_id,
            answer=result.answer,
            usage=result.usage,
            elapsed_ms=result.elapsed_ms,
        )

    def stream(
        self,
        user_input: str,
        *,
        thread_id: str | None = None,
        retrieval_profile: RetrievalProfile | None = None,
        user_id: int | None = None,
        kb_id: int | None = None,
        db_session: Session | None = None,
        system_prompt: str | None = None,
    ) -> Generator[RagStreamEvent, None, None]:
        resolved_thread_id = thread_id or new_thread_id()
        started_at = time.perf_counter()

        answer_parts: list[str] = []
        status_lines: list[str] = []
        citations: list[Citation] = []
        seen_citations: set[tuple[Any, ...]] = set()
        usage: dict[str, Any] | None = None

        for event in self._client.stream(
            user_input,
            thread_id=resolved_thread_id,
            retrieval_profile=retrieval_profile,
            user_id=user_id,
            kb_id=kb_id,
            db_session=db_session,
            system_prompt=system_prompt,
        ):
            if event.type == "messages-tuple":
                event_type = event.data.get("type")
                if event_type == "ai":
                    tool_calls = event.data.get("tool_calls") or []
                    if tool_calls:
                        for tool_call in tool_calls:
                            status_line = f"调用工具 {tool_call.get('name')}"
                            status_lines.append(status_line)
                            yield RagStreamEvent(
                                type="tool_call",
                                tool_name=tool_call.get("name"),
                                status_line=status_line,
                            )
                        continue

                    content = event.data.get("content", "")
                    if content:
                        answer_parts.append(content)
                        yield RagStreamEvent(
                            type="answer",
                            content=content,
                            answer="".join(answer_parts),
                        )
                    continue

                if event_type == "tool":
                    status_line = f"{event.data.get('name')} 已返回结果"
                    status_lines.append(status_line)
                    new_citations: list[Citation] = []
                    for citation in event.data.get("citations") or []:
                        key = citation_key(citation)
                        if key in seen_citations:
                            continue
                        seen_citations.add(key)
                        citations.append(citation)
                        new_citations.append(citation)

                    yield RagStreamEvent(
                        type="tool_result",
                        tool_name=event.data.get("name"),
                        status_line=status_line,
                        content=event.data.get("content", ""),
                        citations=new_citations,
                    )
                    continue

            if event.type == "end":
                usage = event.data.get("usage")

        response = RagResponse(
            thread_id=resolved_thread_id,
            answer="".join(answer_parts),
            status_lines=status_lines,
            citations=citations,
            usage=usage,
            elapsed_ms=int((time.perf_counter() - started_at) * 1000),
        )
        yield RagStreamEvent(
            type="complete",
            answer=response.answer,
            citations=response.citations,
            result=response,
        )


@lru_cache(maxsize=1)
def get_rag_service() -> RagService:
    return RagService()
