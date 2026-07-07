from __future__ import annotations

import re
from typing import Any

from typing_extensions import NotRequired, TypedDict

from app.retrieval.normalizers import normalize_chunk_index, normalize_page

_CITATION_LINE_RE = re.compile(
    r"^\[(?P<rank>\d+)\] source=(?P<source>[^,\n]+)"
    r"(?:, page=(?P<page>[^,\n]+))?"
    r"(?:, chunk=(?P<chunk>[^,\n]+))?$",
    re.MULTILINE,
)


class Citation(TypedDict):
    rank: int
    source: str
    filename: NotRequired[str]
    page: str | None
    chunk_index: int | None
    content: NotRequired[str]
    label: NotRequired[str]

def build_citation_label(*, source: str, page: str | None, chunk_index: int | None) -> str:
    parts = [f"source={source}"]
    if page not in (None, "", "na"):
        parts.append(f"page={page}")
    if chunk_index not in (None, ""):
        parts.append(f"chunk={chunk_index}")
    return ", ".join(parts)


def citation_key(citation: Citation) -> tuple[Any, ...]:
    return (
        citation.get("rank"),
        citation.get("source"),
        citation.get("page"),
        citation.get("chunk_index"),
    )


def with_citation_label(citation: Citation) -> Citation:
    labeled = dict(citation)
    labeled["label"] = build_citation_label(
        source=citation["source"],
        page=citation.get("page"),
        chunk_index=citation.get("chunk_index"),
    )
    return labeled


def _match_to_citation(match: re.Match[str]) -> Citation:
    citation: Citation = {
        "rank": int(match.group("rank")),
        "source": match.group("source"),
        "page": normalize_page(match.group("page")),
        "chunk_index": normalize_chunk_index(match.group("chunk")),
    }
    return with_citation_label(citation)


def extract_citations_from_text(text: str) -> list[Citation]:
    return [_match_to_citation(match) for match in _CITATION_LINE_RE.finditer(text)]


def extract_references_from_text(text: str) -> list[Citation]:
    citations_by_rank = {citation["rank"]: citation for citation in extract_citations_from_text(text)}
    references: list[Citation] = []
    for section in [part.strip() for part in text.split("\n\n") if part.strip()]:
        header, _, content = section.partition("\n")
        match = _CITATION_LINE_RE.match(header)
        if match is None:
            continue
        rank = int(match.group("rank"))
        citation = dict(citations_by_rank.get(rank) or _match_to_citation(match))
        citation["filename"] = citation["source"]
        citation["content"] = content.strip()
        references.append(citation)
    return references
