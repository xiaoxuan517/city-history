from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP
from sqlalchemy import select

from app.db.models.chat import ChatRun
from app.db.models.document import Document
from app.db.session import get_session_factory
from app.retrieval.pgvector_store import retrieve_pgvector_retrieved_chunks
from app.retrieval.profile import RetrievalProfile

mcp = FastMCP(
    "langchain-rag",
    instructions=(
        "Tools for the local multi-tenant enterprise knowledge base. "
        "All tools require explicit user_id and kb_id inputs and preserve SQL-level tenant filtering."
    ),
)


@mcp.tool()
def kb_search(
    user_id: int,
    kb_id: int,
    query: str,
    top_k: int = 3,
    search_type: str = "similarity",
    reranker_enabled: bool = False,
) -> list[dict[str, Any]]:
    """Search chunks in one user's knowledge base using pgvector retrieval."""
    profile = RetrievalProfile.from_settings().with_overrides(
        top_k=top_k,
        search_type=search_type,
        reranker_enabled=reranker_enabled,
    )
    session_factory = get_session_factory()
    with session_factory() as session:
        chunks = retrieve_pgvector_retrieved_chunks(
            session,
            user_id=user_id,
            kb_id=kb_id,
            query=query,
            top_k=profile.top_k,
            search_type=profile.search_type,
            fetch_k=profile.fetch_k,
            reranker_enabled=profile.reranker_enabled,
        )
    return [chunk.to_reference() for chunk in chunks]


@mcp.tool()
def document_lookup(user_id: int, kb_id: int, document_id: int) -> dict[str, Any]:
    """Return document metadata if the document belongs to the user and knowledge base."""
    session_factory = get_session_factory()
    with session_factory() as session:
        statement = select(Document).where(
            Document.id == document_id,
            Document.user_id == user_id,
            Document.kb_id == kb_id,
        )
        document = session.scalar(statement)
        if document is None:
            return {"found": False}
        return {
            "found": True,
            "id": document.id,
            "kb_id": document.kb_id,
            "user_id": document.user_id,
            "filename": document.filename,
            "content_type": document.content_type,
            "status": document.status.value,
            "error_message": document.error_message,
            "created_at": document.created_at.isoformat(),
            "updated_at": document.updated_at.isoformat(),
        }


@mcp.tool()
def get_chat_run(user_id: int, run_id: int) -> dict[str, Any]:
    """Return one chat run if it belongs to the user."""
    session_factory = get_session_factory()
    with session_factory() as session:
        statement = select(ChatRun).where(ChatRun.id == run_id, ChatRun.user_id == user_id)
        run = session.scalar(statement)
        if run is None:
            return {"found": False}
        return {
            "found": True,
            "id": run.id,
            "session_id": run.session_id,
            "user_id": run.user_id,
            "kb_id": run.kb_id,
            "prompt_version_id": run.prompt_version_id,
            "status": run.status.value,
            "question": run.question,
            "answer": run.answer,
            "references": run.references,
            "usage": run.usage,
            "token_cost": run.token_cost,
            "trace_id": run.trace_id,
            "trace_url": run.trace_url,
            "error_message": run.error_message,
            "created_at": run.created_at.isoformat(),
            "updated_at": run.updated_at.isoformat(),
        }


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
