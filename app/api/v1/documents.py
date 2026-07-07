from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, File, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.api.v1.auth import get_current_user
from app.api.errors import ApiError
from app.db.models.user import User
from app.db.session import get_db_session
from app.schemas.document import DocumentProcessResponse, DocumentRead
from app.services.document_service import DocumentNotFoundError, DocumentService, get_document_service
from app.services.hot_question_cache import build_hot_question_scope_key, get_hot_question_cache
from app.services.operation_log_service import OperationLogService, get_operation_log_service
from app.workers.tasks import get_document_task_dispatcher

router = APIRouter(tags=["documents"])
logger = logging.getLogger(__name__)


@router.post("/api/v1/kbs/{kb_id}/documents", response_model=DocumentRead, status_code=status.HTTP_201_CREATED)
async def upload_document(
    kb_id: int,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
    document_service: DocumentService = Depends(get_document_service),
    operation_log_service: OperationLogService = Depends(get_operation_log_service),
    hot_question_cache=Depends(get_hot_question_cache),
    dispatch_document_processing=Depends(get_document_task_dispatcher),
) -> DocumentRead:
    content = await file.read()
    document = document_service.create_upload(
        session,
        user_id=current_user.id,
        kb_id=kb_id,
        filename=file.filename or "upload.bin",
        content_type=file.content_type,
        content=content,
    )

    try:
        dispatch_document_processing(document.id)
    except Exception:
        logger.exception("文档异步处理任务投递失败。document_id=%s", document.id)
    operation_log_service.record(
        session,
        user_id=current_user.id,
        action="document.upload",
        resource_type="document",
        resource_id=document.id,
        details={"kb_id": kb_id, "filename": document.filename, "content_type": document.content_type},
    )
    hot_question_cache.invalidate_scope(scope_key=build_hot_question_scope_key(user_id=current_user.id, kb_id=kb_id))
    return DocumentRead.model_validate(document)


@router.get("/api/v1/kbs/{kb_id}/documents", response_model=list[DocumentRead])
def list_documents(
    kb_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
    document_service: DocumentService = Depends(get_document_service),
) -> list[DocumentRead]:
    documents = document_service.list_for_kb(session, user_id=current_user.id, kb_id=kb_id)
    return [DocumentRead.model_validate(document) for document in documents]


@router.get("/api/v1/documents/{document_id}", response_model=DocumentRead)
def get_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
    document_service: DocumentService = Depends(get_document_service),
) -> DocumentRead:
    document = document_service.get_for_user(session, user_id=current_user.id, document_id=document_id)
    return DocumentRead.model_validate(document)


@router.delete("/api/v1/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
    document_service: DocumentService = Depends(get_document_service),
    operation_log_service: OperationLogService = Depends(get_operation_log_service),
    hot_question_cache=Depends(get_hot_question_cache),
) -> Response:
    document = document_service.get_for_user(session, user_id=current_user.id, document_id=document_id)
    document_service.delete(session, user_id=current_user.id, document_id=document_id)
    operation_log_service.record(
        session,
        user_id=current_user.id,
        action="document.delete",
        resource_type="document",
        resource_id=document_id,
    )
    hot_question_cache.invalidate_scope(
        scope_key=build_hot_question_scope_key(user_id=current_user.id, kb_id=document.kb_id)
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)



@router.post("/api/v1/documents/{document_id}/process", response_model=DocumentProcessResponse)
def process_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
    document_service: DocumentService = Depends(get_document_service),
    operation_log_service: OperationLogService = Depends(get_operation_log_service),
    hot_question_cache=Depends(get_hot_question_cache),
) -> DocumentProcessResponse:
    try:
        document, chunk_count = document_service.process_sync(
            session,
            user_id=current_user.id,
            document_id=document_id,
        )
    except DocumentNotFoundError:
        raise
    except Exception as exc:
        raise ApiError(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code="document_processing_failed",
            message=str(exc),
        ) from exc
    operation_log_service.record(
        session,
        user_id=current_user.id,
        action="document.process",
        resource_type="document",
        resource_id=document.id,
        details={"kb_id": document.kb_id, "chunk_count": chunk_count, "status": document.status.value},
    )
    hot_question_cache.invalidate_scope(
        scope_key=build_hot_question_scope_key(user_id=current_user.id, kb_id=document.kb_id)
    )
    return DocumentProcessResponse(
        document=DocumentRead.model_validate(document),
        parsed_units=chunk_count,
        chunk_count=chunk_count,
    )
