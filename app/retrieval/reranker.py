from __future__ import annotations

import math
import re
from dataclasses import dataclass

from langchain_core.documents import Document

from app.config.settings import settings
from app.retrieval.embeddings import get_embeddings

_SUPPORTED_RERANKER_STRATEGIES = {"embedding_lexical"}
_TOKEN_RE = re.compile(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]")
_EMBEDDING_WEIGHT = 0.85
_LEXICAL_WEIGHT = 0.15


@dataclass(frozen=True)
class RerankedDocument:
    rank: int
    score: float
    lexical_score: float
    embedding_score: float
    document: Document


def normalize_reranker_strategy(strategy: str | None = None) -> str:
    resolved = (strategy or settings.reranker_strategy).strip().lower()
    if resolved not in _SUPPORTED_RERANKER_STRATEGIES:
        supported = ", ".join(sorted(_SUPPORTED_RERANKER_STRATEGIES))
        raise ValueError(f"RERANKER_STRATEGY must be one of [{supported}], got: {resolved}")
    return resolved


def _tokenize(text: str) -> set[str]:
    tokens = {token.lower() for token in _TOKEN_RE.findall(text)}
    return {token for token in tokens if len(token) > 1 or not token.isascii()}


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    dot = sum(left_value * right_value for left_value, right_value in zip(left, right, strict=False))
    return dot / (left_norm * right_norm)


def _lexical_overlap_score(query: str, doc: Document) -> float:
    query_terms = _tokenize(query)
    if not query_terms:
        return 0.0

    metadata = doc.metadata or {}
    doc_text = " ".join(
        [
            doc.page_content,
            str(metadata.get("source", "")),
            str(metadata.get("page", "")),
        ]
    )
    doc_terms = _tokenize(doc_text)
    if not doc_terms:
        return 0.0

    return len(query_terms & doc_terms) / len(query_terms)


def rerank_documents(
    query: str,
    documents: list[Document],
    *,
    top_k: int,
    strategy: str | None = None,
) -> list[Document]:
    if not documents:
        return []

    normalize_reranker_strategy(strategy)
    embeddings = get_embeddings()
    query_vector = embeddings.embed_query(query)
    doc_vectors = embeddings.embed_documents([document.page_content for document in documents])

    scored_documents: list[RerankedDocument] = []
    for index, (document, doc_vector) in enumerate(zip(documents, doc_vectors, strict=False), start=1):
        embedding_score = _cosine_similarity(query_vector, doc_vector)
        lexical_score = _lexical_overlap_score(query, document)
        score = (_EMBEDDING_WEIGHT * embedding_score) + (_LEXICAL_WEIGHT * lexical_score)
        scored_documents.append(
            RerankedDocument(
                rank=index,
                score=score,
                lexical_score=lexical_score,
                embedding_score=embedding_score,
                document=document,
            )
        )

    reranked = sorted(scored_documents, key=lambda item: item.score, reverse=True)
    return [item.document for item in reranked[:top_k]]
