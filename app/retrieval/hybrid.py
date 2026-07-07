from __future__ import annotations

from typing import Any

from langchain_core.documents import Document

from app.retrieval.filters import MetadataFilter
from app.retrieval.lexical import document_key, rank_lexical_documents

DEFAULT_RRF_K = 60
DEFAULT_LEXICAL_WEIGHT = 1.0


def load_index_documents(vector_store, *, metadata_filter: MetadataFilter | None = None) -> list[Document]:
    raw = vector_store.get(
        where=metadata_filter,
        include=["documents", "metadatas"],
    )
    ids = raw.get("ids") or []
    documents = raw.get("documents") or []
    metadatas = raw.get("metadatas") or []

    return [
        Document(
            id=doc_id,
            page_content=content or "",
            metadata=metadata or {},
        )
        for doc_id, content, metadata in zip(ids, documents, metadatas, strict=False)
    ]


def rrf_fuse_documents(
    dense_docs: list[Document],
    lexical_docs: list[Document],
    *,
    top_k: int,
    rrf_k: int = DEFAULT_RRF_K,
    lexical_weight: float = DEFAULT_LEXICAL_WEIGHT,
) -> list[Document]:
    scores: dict[tuple[Any, ...], float] = {}
    docs_by_key: dict[tuple[Any, ...], Document] = {}

    for rank, doc in enumerate(dense_docs, start=1):
        key = document_key(doc)
        scores[key] = scores.get(key, 0.0) + 1.0 / (rrf_k + rank)
        docs_by_key.setdefault(key, doc)

    for rank, doc in enumerate(lexical_docs, start=1):
        key = document_key(doc)
        scores[key] = scores.get(key, 0.0) + lexical_weight / (rrf_k + rank)
        docs_by_key.setdefault(key, doc)

    ranked_keys = sorted(scores, key=lambda key: scores[key], reverse=True)
    return [docs_by_key[key] for key in ranked_keys[:top_k]]


def hybrid_search_documents(
    query: str,
    *,
    vector_store,
    top_k: int,
    dense_k: int,
    lexical_k: int,
    metadata_filter: MetadataFilter | None = None,
) -> list[Document]:
    dense_docs = vector_store.similarity_search(query, k=dense_k, filter=metadata_filter)
    index_docs = load_index_documents(vector_store, metadata_filter=metadata_filter)
    lexical_docs = rank_lexical_documents(query, index_docs, top_k=lexical_k)
    return rrf_fuse_documents(
        dense_docs,
        lexical_docs,
        top_k=top_k,
    )
