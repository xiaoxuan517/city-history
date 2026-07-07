from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from app.config.settings import settings

SUPPORTED_RETRIEVAL_SEARCH_TYPES = {"similarity", "mmr", "hybrid"}


@dataclass(frozen=True)
class RetrievalProfile:
    search_type: str
    top_k: int
    fetch_k: int
    reranker_enabled: bool
    max_context_chars: int

    def __post_init__(self) -> None:
        normalized_search_type = self.search_type.strip().lower()
        if normalized_search_type not in SUPPORTED_RETRIEVAL_SEARCH_TYPES:
            supported = ", ".join(sorted(SUPPORTED_RETRIEVAL_SEARCH_TYPES))
            raise ValueError(f"search_type must be one of [{supported}], got: {self.search_type}")

        if self.top_k <= 0:
            raise ValueError(f"top_k must be > 0, got: {self.top_k}")
        if self.fetch_k <= 0:
            raise ValueError(f"fetch_k must be > 0, got: {self.fetch_k}")
        if self.fetch_k < self.top_k:
            raise ValueError(f"fetch_k must be >= top_k, got fetch_k={self.fetch_k} top_k={self.top_k}")
        if self.max_context_chars <= 0:
            raise ValueError(f"max_context_chars must be > 0, got: {self.max_context_chars}")

        object.__setattr__(self, "search_type", normalized_search_type)

    @classmethod
    def from_settings(cls) -> "RetrievalProfile":
        return cls(
            search_type=settings.retrieval_search_type,
            top_k=settings.top_k,
            fetch_k=settings.retrieval_fetch_k,
            reranker_enabled=settings.reranker_enabled,
            max_context_chars=settings.retrieval_max_context_chars,
        )

    @classmethod
    def from_mapping(cls, payload: dict[str, Any]) -> "RetrievalProfile":
        base = cls.from_settings()
        return base.with_overrides(
            search_type=payload.get("search_type"),
            top_k=payload.get("top_k"),
            fetch_k=payload.get("fetch_k"),
            reranker_enabled=payload.get("reranker_enabled"),
            max_context_chars=payload.get("max_context_chars"),
        )

    def with_overrides(
        self,
        *,
        search_type: str | None = None,
        top_k: int | None = None,
        fetch_k: int | None = None,
        reranker_enabled: bool | None = None,
        max_context_chars: int | None = None,
    ) -> "RetrievalProfile":
        resolved_top_k = top_k or self.top_k
        resolved_fetch_k = max(fetch_k or self.fetch_k, resolved_top_k)
        return RetrievalProfile(
            search_type=search_type or self.search_type,
            top_k=resolved_top_k,
            fetch_k=resolved_fetch_k,
            reranker_enabled=self.reranker_enabled if reranker_enabled is None else reranker_enabled,
            max_context_chars=max_context_chars or self.max_context_chars,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
