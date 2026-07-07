from __future__ import annotations

import os

from app.config.settings import settings


def configure_langsmith_environment() -> None:
    """Expose settings through the environment variables LangChain tracing reads."""
    enabled = "true" if settings.langsmith_tracing else "false"
    os.environ["LANGSMITH_TRACING"] = enabled
    os.environ["LANGCHAIN_TRACING_V2"] = enabled
    os.environ.setdefault("LANGSMITH_PROJECT", settings.langsmith_project)
    os.environ.setdefault("LANGCHAIN_PROJECT", settings.langsmith_project)
    if settings.langsmith_api_key:
        os.environ.setdefault("LANGSMITH_API_KEY", settings.langsmith_api_key)
        os.environ.setdefault("LANGCHAIN_API_KEY", settings.langsmith_api_key)
    if settings.langsmith_endpoint:
        os.environ.setdefault("LANGSMITH_ENDPOINT", settings.langsmith_endpoint)
        os.environ.setdefault("LANGCHAIN_ENDPOINT", settings.langsmith_endpoint)
