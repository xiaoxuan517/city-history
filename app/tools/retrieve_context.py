import logging

from langchain.tools import ToolRuntime
from langchain_core.tools import tool
from sqlalchemy.orm import Session

from app.retrieval.formatter import format_retrieved_chunks
from app.retrieval.pgvector_store import retrieve_pgvector_retrieved_chunks
from app.retrieval.profile import RetrievalProfile

logger = logging.getLogger(__name__)


def _profile_from_runtime(runtime: ToolRuntime | None) -> RetrievalProfile:
    if runtime is None:
        return RetrievalProfile.from_settings()

    payload = (runtime.context or {}).get("retrieval_profile")
    if isinstance(payload, dict):
        return RetrievalProfile.from_mapping(payload)
    return RetrievalProfile.from_settings()


def _context_from_runtime(runtime: ToolRuntime) -> tuple[Session, int, int]:
    context = runtime.context or {}
    db_session = context.get("db_session")
    user_id = context.get("user_id")
    kb_id = context.get("kb_id")
    if not isinstance(db_session, Session) or not isinstance(user_id, int) or not isinstance(kb_id, int):
        raise ValueError("retrieve_context requires db_session, user_id, and kb_id in tool runtime context")
    return db_session, user_id, kb_id


@tool
def retrieve_context(query: str, runtime: ToolRuntime, source: str | None = None) -> str:
    """Must-use tool for questions about the indexed local knowledge base.

    Args:
        query: Search query for the local knowledge base.
        source: Optional exact source metadata filter, such as "维护保养.txt".
    """
    profile = _profile_from_runtime(runtime)
    db_session, user_id, kb_id = _context_from_runtime(runtime)
    logger.info(
        "工具调用：retrieve_context。user_id=%s kb_id=%s query_chars=%s top_k=%s search_type=%s reranker_enabled=%s source=%s",
        user_id,
        kb_id,
        len(query),
        profile.top_k,
        profile.search_type,
        profile.reranker_enabled,
        source,
    )
    try:
        chunks = retrieve_pgvector_retrieved_chunks(
            db_session,
            user_id=user_id,
            kb_id=kb_id,
            query=query,
            top_k=profile.top_k,
            search_type=profile.search_type,
            fetch_k=profile.fetch_k,
            reranker_enabled=profile.reranker_enabled,
        )
        if source:
            chunks = [chunk for chunk in chunks if chunk.source == source]
        logger.info("工具执行完成：retrieve_context。hit_count=%s", len(chunks))
        logger.debug("检索到的文档详情：%s", [chunk.content for chunk in chunks])
        return format_retrieved_chunks(chunks, max_context_chars=profile.max_context_chars)
    except Exception:
        logger.exception("工具执行失败：retrieve_context")
        raise
