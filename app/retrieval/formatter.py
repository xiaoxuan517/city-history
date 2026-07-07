from __future__ import annotations

from typing import Any, Mapping

from app.config.settings import settings
from app.retrieval.citations import Citation, build_citation_label
from app.retrieval.normalizers import normalize_chunk_index, normalize_page, single_line_preview
from app.retrieval.types import RetrievedChunk

_CHUNK_PREVIEW_WIDTH = 1200
_MIN_CONTENT_PREVIEW_WIDTH = 80

def _compose_citation_label(*, source: str, page: str | None, chunk_index: int | None) -> str:
    return build_citation_label(
        source=source,
        page=page,
        chunk_index=chunk_index,
    )


def _citation_parts(citation: Mapping[str, Any] | RetrievedChunk) -> tuple[str, str | None, int | None]:
    if isinstance(citation, RetrievedChunk):
        return citation.source, citation.page, citation.chunk_index
    return (
        str(citation.get("source", "unknown")),
        normalize_page(citation.get("page")),
        normalize_chunk_index(citation.get("chunk_index")),
    )


def format_citation_label(citation: Citation | RetrievedChunk) -> str:
    source, page, chunk_index = _citation_parts(citation)
    return _compose_citation_label(
        source=source,
        page=page,
        chunk_index=chunk_index,
    )


def format_chunk_for_context(chunk: RetrievedChunk) -> str:
    content = single_line_preview(chunk.content, width=_CHUNK_PREVIEW_WIDTH)
    return f"[{chunk.rank}] {format_citation_label(chunk)}\n{content}"


def _chunk_dedupe_key(chunk: RetrievedChunk) -> tuple[Any, ...]:
    content_hash = chunk.metadata.get("content_hash")
    if content_hash:
        return ("content_hash", content_hash)

    return (
        "content",
        chunk.source,
        chunk.page,
        chunk.content,
    )


def _dedupe_chunks(chunks: list[RetrievedChunk]) -> tuple[list[RetrievedChunk], int]:
    deduped: list[RetrievedChunk] = []
    seen_keys: set[tuple[Any, ...]] = set()

    for chunk in chunks:
        key = _chunk_dedupe_key(chunk)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        deduped.append(chunk)

    return deduped, len(chunks) - len(deduped)


def _format_chunk_with_budget(chunk: RetrievedChunk, *, remaining_chars: int) -> str:
    header = f"[{chunk.rank}] {format_citation_label(chunk)}\n"
    if remaining_chars <= len(header):
        return header.rstrip()

    content_budget = max(min(remaining_chars - len(header), _CHUNK_PREVIEW_WIDTH), _MIN_CONTENT_PREVIEW_WIDTH)
    content = single_line_preview(chunk.content, width=content_budget)
    return f"{header}{content}"


def format_retrieved_chunks(chunks: list[RetrievedChunk], *, max_context_chars: int | None = None) -> str:
    if not chunks:
        return "No relevant context found."

    resolved_max_context_chars = max_context_chars or settings.retrieval_max_context_chars
    unique_chunks, deduped_count = _dedupe_chunks(chunks)

    formatted_chunks: list[str] = []
    consumed_chars = 0
    truncated_count = 0

    for chunk in unique_chunks:
        separator = "\n\n" if formatted_chunks else ""
        remaining_chars = resolved_max_context_chars - consumed_chars - len(separator)
        if remaining_chars <= 0:
            truncated_count += 1
            continue

        formatted_chunk = _format_chunk_with_budget(chunk, remaining_chars=remaining_chars)
        candidate = f"{separator}{formatted_chunk}"
        if len(candidate) > remaining_chars and formatted_chunks:
            truncated_count += 1
            continue

        formatted_chunks.append(formatted_chunk)
        consumed_chars += len(candidate)

    omitted_after_budget = max(len(unique_chunks) - len(formatted_chunks), 0)
    summary_parts: list[str] = []
    if deduped_count > 0:
        summary_parts.append(f"deduped={deduped_count}")
    if truncated_count > 0 or omitted_after_budget > 0:
        summary_parts.append(f"truncated={max(truncated_count, omitted_after_budget)}")

    if summary_parts:
        formatted_chunks.append("Context summary: " + ", ".join(summary_parts))

    return "\n\n".join(formatted_chunks)
