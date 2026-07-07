from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class RetrievedChunk:
    content: str
    source: str
    metadata: dict[str, Any]
    rank: int | None = None
    document_id: int | str | None = None
    chunk_id: int | str | None = None
    chunk_index: int | None = None
    page: str | None = None
    score: float | None = None

    def to_reference(self) -> dict[str, Any]:
        reference: dict[str, Any] = {
            "document_id": self.document_id,
            "filename": self.source,
            "chunk_id": self.chunk_id,
            "chunk_index": self.chunk_index,
            "content": self.content,
        }
        if self.page is not None:
            reference["page"] = self.page
        if self.score is not None:
            reference["score"] = self.score
        return reference


class Retriever(Protocol):
    def retrieve(self, query: str, *, top_k: int) -> list[RetrievedChunk]:
        ...
