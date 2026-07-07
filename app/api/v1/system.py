from __future__ import annotations

from pydantic import BaseModel
from fastapi import APIRouter

from app.config.settings import settings
from app.services.metrics_service import get_metrics_service

router = APIRouter(prefix="/api/v1", tags=["system"])


class HealthResponse(BaseModel):
    status: str


class PublicConfigResponse(BaseModel):
    chat_model: str
    embedding_model: str
    embedding_dimension: int
    top_k: int
    retrieval_search_type: str
    retrieval_fetch_k: int
    reranker_enabled: bool
    reranker_strategy: str
    retrieval_max_context_chars: int


class MetricsResponse(BaseModel):
    started_at: str
    uptime_seconds: int
    chat_requests_total: int
    chat_stream_requests_total: int
    chat_errors_total: int
    feedback_total: int
    feedback_up_total: int
    feedback_down_total: int
    average_chat_elapsed_ms: float | None
    last_chat_elapsed_ms: int | None


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get("/config", response_model=PublicConfigResponse)
def public_config() -> PublicConfigResponse:
    return PublicConfigResponse(
        chat_model=settings.chat_model,
        embedding_model=settings.embedding_model,
        embedding_dimension=settings.embedding_dimension,
        top_k=settings.top_k,
        retrieval_search_type=settings.retrieval_search_type,
        retrieval_fetch_k=settings.retrieval_fetch_k,
        reranker_enabled=settings.reranker_enabled,
        reranker_strategy=settings.reranker_strategy,
        retrieval_max_context_chars=settings.retrieval_max_context_chars,
    )


@router.get("/metrics", response_model=MetricsResponse)
def metrics() -> MetricsResponse:
    return MetricsResponse(**get_metrics_service().snapshot_dict())
