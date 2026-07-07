from __future__ import annotations

import logging
from collections import Counter
from pathlib import Path

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.config.settings import settings

logger = logging.getLogger(__name__)

_DEFAULT_SEPARATORS = ["\n\n", "\n", "。", "；", "，", " ", ""]
_MARKDOWN_SEPARATORS = ["\n## ", "\n### ", "\n#### ", "\n\n", "\n", "。", "；", "，", " ", ""]
_PDF_SEPARATORS = ["\n\n", "\n", "。", "；", "，", " ", ""]
_HTML_SEPARATORS = ["\n\n", "\n", "。", "；", "，", " ", ""]
_DOCX_SEPARATORS = ["\n\n", "\n", "。", "；", "，", " ", ""]


def _document_type(doc: Document) -> str:
    metadata = doc.metadata or {}
    document_type = str(metadata.get("document_type") or "").strip().lower()
    if document_type:
        return document_type

    suffix = Path(str(metadata.get("source") or "")).suffix.lower()
    if suffix == ".pdf":
        return "pdf"
    if suffix == ".md":
        return "markdown"
    if suffix == ".docx":
        return "docx"
    if suffix in {".html", ".htm"}:
        return "html"
    if suffix == ".txt":
        return "text"
    return "unknown"


def _splitter_for_document_type(document_type: str) -> RecursiveCharacterTextSplitter:
    if document_type == "markdown":
        return RecursiveCharacterTextSplitter(
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
            separators=_MARKDOWN_SEPARATORS,
        )

    if document_type == "pdf":
        chunk_size = max(500, int(settings.chunk_size * 0.9))
        chunk_overlap = min(settings.chunk_overlap, max(chunk_size // 4, 1))
        return RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=_PDF_SEPARATORS,
        )

    if document_type == "html":
        return RecursiveCharacterTextSplitter(
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
            separators=_HTML_SEPARATORS,
        )

    if document_type == "docx":
        return RecursiveCharacterTextSplitter(
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
            separators=_DOCX_SEPARATORS,
        )

    return RecursiveCharacterTextSplitter(
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
        separators=_DEFAULT_SEPARATORS,
    )


def split_documents_by_type(docs: list[Document]) -> list[Document]:
    split_docs: list[Document] = []
    raw_counts: Counter[str] = Counter()
    split_counts: Counter[str] = Counter()

    for doc in docs:
        document_type = _document_type(doc)
        raw_counts[document_type] += 1
        splitter = _splitter_for_document_type(document_type)
        chunks = splitter.split_documents([doc])
        for chunk in chunks:
            metadata = dict(chunk.metadata or {})
            metadata["document_type"] = document_type
            chunk.metadata = metadata
        split_docs.extend(chunks)
        split_counts[document_type] += len(chunks)

    logger.info(
        "按文档类型切分完成。raw_counts=%s split_counts=%s",
        dict(raw_counts),
        dict(split_counts),
    )
    return split_docs
