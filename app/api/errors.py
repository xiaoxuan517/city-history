from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.services.chat_service import ChatSessionNotFoundError
from app.services.document_service import DocumentNotFoundError
from app.services.kb_service import KnowledgeBaseNotFoundError


@dataclass(frozen=True)
class ApiErrorSpec:
    status_code: int
    code: str


class ApiError(Exception):
    def __init__(
        self,
        *,
        status_code: int,
        code: str,
        message: str,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.headers = headers


_ERROR_SPECS: dict[type[Exception], ApiErrorSpec] = {
    KnowledgeBaseNotFoundError: ApiErrorSpec(status.HTTP_404_NOT_FOUND, "knowledge_base_not_found"),
    DocumentNotFoundError: ApiErrorSpec(status.HTTP_404_NOT_FOUND, "document_not_found"),
    ChatSessionNotFoundError: ApiErrorSpec(status.HTTP_404_NOT_FOUND, "chat_session_not_found"),
}


def error_response(*, status_code: int, code: str, message: str, headers: dict[str, str] | None = None) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message}},
        headers=headers,
    )


def _handler_for(spec: ApiErrorSpec) -> Callable[[Request, Exception], JSONResponse]:
    def handler(_: Request, exc: Exception) -> JSONResponse:
        return error_response(status_code=spec.status_code, code=spec.code, message=str(exc))

    return handler


def api_error_handler(_: Request, exc: ApiError) -> JSONResponse:
    return error_response(
        status_code=exc.status_code,
        code=exc.code,
        message=exc.message,
        headers=exc.headers,
    )


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(ApiError, api_error_handler)
    for exception_class, spec in _ERROR_SPECS.items():
        app.add_exception_handler(exception_class, _handler_for(spec))
