from __future__ import annotations

from typing import Any

from langchain.agents.middleware import ModelRequest

from app.retrieval.profile import RetrievalProfile


def _message_type(message: Any) -> str | None:
    return getattr(message, "type", None)


def _count_messages(messages: list[Any], message_type: str) -> int:
    return sum(1 for message in messages if _message_type(message) == message_type)


def _resolve_thread_id(request: ModelRequest) -> str:
    runtime = getattr(request, "runtime", None)
    context = getattr(runtime, "context", None) or {}
    thread_id = context.get("thread_id")
    if thread_id:
        return str(thread_id)
    return "unknown"


def _resolve_retrieval_profile(request: ModelRequest) -> RetrievalProfile:
    runtime = getattr(request, "runtime", None)
    context = getattr(runtime, "context", None) or {}
    payload = context.get("retrieval_profile")
    if isinstance(payload, dict):
        return RetrievalProfile.from_mapping(payload)
    return RetrievalProfile.from_settings()


def build_runtime_prompt(request: ModelRequest) -> str:
    messages = list(request.state.get("messages", []))
    user_turns = _count_messages(messages, "human")
    tool_messages = _count_messages(messages, "tool")
    prior_turns = max(user_turns - 1, 0)
    conversation_mode = "follow_up" if prior_turns > 0 else "first_turn"
    profile = _resolve_retrieval_profile(request)

    return (
        "Runtime context:\n"
        f"- thread_id: {_resolve_thread_id(request)}\n"
        f"- conversation_mode: {conversation_mode}\n"
        f"- prior_user_turns: {prior_turns}\n"
        f"- observed_tool_messages: {tool_messages}\n"
        f"- retrieval_search_type: {profile.search_type}\n"
        f"- retrieval_top_k: {profile.top_k}\n"
        f"- retrieval_fetch_k: {profile.fetch_k}\n"
        f"- retrieval_reranker_enabled: {profile.reranker_enabled}\n"
        f"- retrieval_max_context_chars: {profile.max_context_chars}\n"
        "Prompt strategy:\n"
        "- Treat the retrieve_context tool as the only path to knowledge-base facts.\n"
        "- If the user explicitly asks about a known source file, pass that exact source to retrieve_context.\n"
        "- On follow-up turns, maintain conversational continuity, but still retrieve before making factual claims about the indexed corpus.\n"
        "- Use citations when grounded context is available; otherwise refuse briefly instead of improvising.\n"
    )
