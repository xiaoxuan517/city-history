from __future__ import annotations

import re
from typing import Any

from langchain_core.documents import Document

_LATIN_TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.+-]*")
_CHINESE_RUN_RE = re.compile(r"[\u4e00-\u9fff]+")
_STOP_TERMS = {
    "一下",
    "一直",
    "一般",
    "什么",
    "使用",
    "先做",
    "应该",
    "怎么",
    "怎样",
    "情况",
    "时候",
    "机器人",
    "扫地",
    "需要",
    "这种",
}


def _chinese_ngrams(text: str) -> list[str]:
    terms: list[str] = []
    for match in _CHINESE_RUN_RE.finditer(text):
        run = match.group(0)
        for size in (2, 3, 4):
            if len(run) < size:
                continue
            terms.extend(run[index : index + size] for index in range(0, len(run) - size + 1))
    return terms


def query_terms(query: str) -> list[str]:
    terms = [match.group(0).lower() for match in _LATIN_TOKEN_RE.finditer(query)]
    terms.extend(term.lower() for term in _chinese_ngrams(query))
    return list(dict.fromkeys(term for term in terms if term not in _STOP_TERMS))


def lexical_score(query: str, doc: Document) -> int:
    content = doc.page_content.lower()
    score = 0
    for term in query_terms(query):
        if term in content:
            score += 2 if len(term) >= 3 else 1
    return score


def rank_lexical_documents(query: str, docs: list[Document], *, top_k: int) -> list[Document]:
    scored: list[tuple[int, int, Document]] = []
    for doc in docs:
        score = lexical_score(query, doc)
        if score <= 0:
            continue
        scored.append((score, -len(doc.page_content), doc))

    return [doc for _, _, doc in sorted(scored, key=lambda item: item[:2], reverse=True)[:top_k]]


def document_key(doc: Document) -> tuple[Any, ...]:
    metadata = doc.metadata or {}
    content_hash = metadata.get("content_hash")
    if content_hash:
        return ("content_hash", content_hash)
    return (
        getattr(doc, "id", None),
        metadata.get("source"),
        metadata.get("page"),
        metadata.get("chunk_index"),
    )
