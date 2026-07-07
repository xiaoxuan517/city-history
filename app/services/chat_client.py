from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Generator
from uuid import uuid4

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from sqlalchemy.orm import Session

from app.agent.create_agent import build_agent
from app.retrieval.citations import extract_references_from_text
from app.retrieval.profile import RetrievalProfile

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class StreamEvent:
    """A single event from the streaming agent response.

    Event types align with the LangGraph SSE protocol:
        - ``"values"``: Full state snapshot.
        - ``"messages-tuple"``: Per-message update.
        - ``"end"``: Stream finished.
    """

    type: str
    data: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ChatResult:
    answer: str
    usage: dict[str, Any] | None = None
    elapsed_ms: int | None = None


def new_thread_id(prefix: str = "chat") -> str:
    return f"{prefix}_{uuid4().hex}"


def _build_request_config(
    thread_id: str,
    *,
    retrieval_profile: RetrievalProfile | None = None,
    user_id: int | None = None,
    kb_id: int | None = None,
    db_session: Session | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    config = {"configurable": {"thread_id": thread_id}}
    context: dict[str, Any] = {"thread_id": thread_id}
    if retrieval_profile is not None:
        context["retrieval_profile"] = retrieval_profile.to_dict()
    if user_id is not None:
        context["user_id"] = user_id
    if kb_id is not None:
        context["kb_id"] = kb_id
    if db_session is not None:
        context["db_session"] = db_session
    return config, context


def _stringify_content(content: Any) -> str:
    if isinstance(content, str):
        return content

    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(item.get("text", ""))
            else:
                parts.append(str(item))
        return "\n".join(part for part in parts if part)

    return str(content)


def _normalize_user_input(text: str) -> str:
    normalized = text.encode("utf-8", errors="replace").decode("utf-8")
    if normalized != text:
        logger.warning("检测到不可编码字符，已使用替代字符归一化输入。")
    return normalized


def _accumulate_usage(
    msg: AIMessage,
    *,
    msg_id: str | None,
    usage_message_ids: set[str],
    cumulative_usage: dict[str, int],
) -> None:
    usage = getattr(msg, "usage_metadata", None)
    if not usage:
        return

    if msg_id in usage_message_ids:
        return

    if msg_id:
        usage_message_ids.add(msg_id)

    cumulative_usage["input_tokens"] += usage.get("input_tokens", 0) or 0
    cumulative_usage["output_tokens"] += usage.get("output_tokens", 0) or 0
    cumulative_usage["total_tokens"] += usage.get("total_tokens", 0) or 0


class AgentChatClient:
    def __init__(self) -> None:
        logger.info("初始化 Agent 客户端。")
        self._agents_by_prompt: dict[str, Any] = {}
        self._default_agent = self._get_agent()

    @property
    def agent(self):
        return self._default_agent

    def _get_agent(self, system_prompt: str | None = None):
        cache_key = system_prompt or ""
        if cache_key not in self._agents_by_prompt:
            self._agents_by_prompt[cache_key] = build_agent(system_prompt=system_prompt)
        return self._agents_by_prompt[cache_key]

    def ask(
        self,
        user_input: str,
        thread_id: str,
        *,
        retrieval_profile: RetrievalProfile | None = None,
        user_id: int | None = None,
        kb_id: int | None = None,
        db_session: Session | None = None,
        system_prompt: str | None = None,
    ) -> ChatResult:
        user_input = _normalize_user_input(user_input)
        logger.info("收到聊天请求。thread_id=%s chars=%s", thread_id, len(user_input))
        started_at = time.perf_counter()
        config, context = _build_request_config(
            thread_id,
            retrieval_profile=retrieval_profile,
            user_id=user_id,
            kb_id=kb_id,
            db_session=db_session,
        )
        agent = self._get_agent(system_prompt)
        result = agent.invoke(
            {"messages": [{"role": "user", "content": user_input}]},
            config=config,
            context=context,
        )
        elapsed_ms = int((time.perf_counter() - started_at) * 1000)
        final_msg = result["messages"][-1]
        answer = _stringify_content(final_msg.content)
        usage = getattr(final_msg, "usage_metadata", None)
        logger.info(
            "聊天请求完成。thread_id=%s answer_chars=%s elapsed_ms=%s",
            thread_id,
            len(answer),
            elapsed_ms,
        )
        return ChatResult(answer=answer, usage=usage, elapsed_ms=elapsed_ms)

    def _serialize_message(self, message: BaseMessage) -> dict[str, Any]:
        base = {
            "id": getattr(message, "id", None),
            "type": message.type,
            "content": _stringify_content(getattr(message, "content", "")),
        }

        if isinstance(message, HumanMessage):
            base["role"] = "user"
            return base

        if isinstance(message, ToolMessage):
            base["role"] = "tool"
            base["name"] = getattr(message, "name", None)
            base["tool_call_id"] = getattr(message, "tool_call_id", None)
            return base

        if isinstance(message, AIMessage):
            base["role"] = "assistant"
            base["tool_calls"] = getattr(message, "tool_calls", []) or []
            usage_metadata = getattr(message, "usage_metadata", None)
            if usage_metadata:
                base["usage_metadata"] = usage_metadata
            return base

        return base

    def _get_existing_message_ids(self, agent, config: dict[str, Any]) -> set[str]:
        snapshot = agent.get_state(config)
        values = getattr(snapshot, "values", {}) or {}
        messages = values.get("messages", []) or []
        existing_ids: set[str] = set()
        for message in messages:
            message_id = getattr(message, "id", None)
            if message_id:
                existing_ids.add(message_id)
        return existing_ids

    def stream(
        self,
        message: str,
        *,
        thread_id: str | None = None,
        retrieval_profile: RetrievalProfile | None = None,
        user_id: int | None = None,
        kb_id: int | None = None,
        db_session: Session | None = None,
        system_prompt: str | None = None,
        **kwargs,
    ) -> Generator[StreamEvent, None, None]:
        """Stream a conversation turn, yielding events incrementally.

        Each call sends one user message and yields events until the agent
        finishes its turn. A ``checkpointer`` must be provided at init time
        for multi-turn context to be preserved across calls.

        Event types align with the LangGraph SSE protocol so consumers can
        share one event-handling path across embedded and HTTP streaming.
        """
        del kwargs

        if thread_id is None:
            thread_id = new_thread_id()

        message = _normalize_user_input(message)
        logger.info("开始流式聊天。thread_id=%s chars=%s", thread_id, len(message))

        state: dict[str, Any] = {"messages": [HumanMessage(content=message)]}
        config, context = _build_request_config(
            thread_id,
            retrieval_profile=retrieval_profile,
            user_id=user_id,
            kb_id=kb_id,
            db_session=db_session,
        )

        agent = self._get_agent(system_prompt)
        seen_ids = self._get_existing_message_ids(agent, config)
        seen_tool_calls: set[str] = set()
        seen_tool_results: set[str] = set()
        usage_message_ids: set[str] = set()
        cumulative_usage: dict[str, int] = {
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
        }

        for mode, chunk in agent.stream(
            state,
            config=config,
            context=context,
            stream_mode=["messages", "updates", "values"],
        ):
            if mode == "messages":
                message_chunk, metadata = chunk
                if metadata.get("langgraph_node") != "model":
                    continue

                text = _stringify_content(getattr(message_chunk, "content", message_chunk))
                if not text:
                    continue

                yield StreamEvent(
                    type="messages-tuple",
                    data={
                        "type": "ai",
                        "content": text,
                        "id": getattr(message_chunk, "id", None),
                    },
                )
                continue

            if mode == "updates":
                for node_data in chunk.values():
                    for msg in node_data.get("messages", []):
                        msg_id = getattr(msg, "id", None)

                        if isinstance(msg, AIMessage):
                            _accumulate_usage(
                                msg,
                                msg_id=msg_id,
                                usage_message_ids=usage_message_ids,
                                cumulative_usage=cumulative_usage,
                            )

                            if msg.tool_calls:
                                tool_calls = []
                                for tool_call in msg.tool_calls:
                                    call_id = tool_call.get("id") or f"{tool_call.get('name')}:{tool_call.get('args')}"
                                    if call_id in seen_tool_calls:
                                        continue
                                    seen_tool_calls.add(call_id)
                                    tool_calls.append(
                                        {
                                            "name": tool_call["name"],
                                            "args": tool_call["args"],
                                            "id": tool_call.get("id"),
                                        }
                                    )
                                if tool_calls:
                                    yield StreamEvent(
                                        type="messages-tuple",
                                        data={
                                            "type": "ai",
                                            "content": "",
                                            "id": msg_id,
                                            "tool_calls": tool_calls,
                                        },
                                    )
                            continue

                        if isinstance(msg, ToolMessage):
                            result_key = getattr(msg, "tool_call_id", None) or msg_id
                            if result_key in seen_tool_results:
                                continue
                            seen_tool_results.add(result_key)
                            tool_content = _stringify_content(msg.content)
                            yield StreamEvent(
                                type="messages-tuple",
                                data={
                                    "type": "tool",
                                    "content": tool_content,
                                    "name": getattr(msg, "name", None),
                                    "tool_call_id": getattr(msg, "tool_call_id", None),
                                    "id": msg_id,
                                    "citations": extract_references_from_text(tool_content),
                                },
                            )
                continue

            if mode != "values":
                continue

            messages = chunk.get("messages", [])

            for msg in messages:
                msg_id = getattr(msg, "id", None)
                if msg_id and msg_id in seen_ids:
                    continue
                if msg_id:
                    seen_ids.add(msg_id)

                if isinstance(msg, AIMessage):
                    _accumulate_usage(
                        msg,
                        msg_id=msg_id,
                        usage_message_ids=usage_message_ids,
                        cumulative_usage=cumulative_usage,
                    )

            yield StreamEvent(
                type="values",
                data={
                    "title": chunk.get("title"),
                    "messages": [self._serialize_message(msg) for msg in messages],
                    "artifacts": chunk.get("artifacts", []),
                },
            )

        logger.info("流式聊天完成。thread_id=%s", thread_id)
        yield StreamEvent(type="end", data={"usage": cumulative_usage})


@lru_cache(maxsize=1)
def get_chat_client() -> AgentChatClient:
    return AgentChatClient()
