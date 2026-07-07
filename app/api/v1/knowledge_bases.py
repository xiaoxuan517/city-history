from __future__ import annotations

import logging
import mimetypes

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.api.v1.auth import get_current_user
from app.db.models.user import User
from app.db.session import get_db_session
from app.schemas.document import DocumentRead
from app.schemas.knowledge_base import (
    KnowledgeBaseCreate,
    KnowledgeBaseFromDownloadRequest,
    KnowledgeBaseRead,
    KnowledgeBaseUpdate,
    KnowledgeBaseWithDocumentResponse,
)
from app.services.alist_service import AListService, get_alist_service
from app.services.document_service import DocumentService, get_document_service
from app.services.hot_question_cache import build_hot_question_scope_key, get_hot_question_cache
from app.services.kb_service import KnowledgeBaseService, get_kb_service
from app.services.operation_log_service import OperationLogService, get_operation_log_service
from app.workers.tasks import get_document_task_dispatcher

router = APIRouter(prefix="/api/v1/kbs", tags=["knowledge_bases"])
logger = logging.getLogger(__name__)


@router.post("", response_model=KnowledgeBaseRead, status_code=status.HTTP_201_CREATED)
def create_knowledge_base(
    payload: KnowledgeBaseCreate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
    kb_service: KnowledgeBaseService = Depends(get_kb_service),
    operation_log_service: OperationLogService = Depends(get_operation_log_service),
) -> KnowledgeBaseRead:
    knowledge_base = kb_service.create(session, user_id=current_user.id, payload=payload)
    operation_log_service.record(
        session,
        user_id=current_user.id,
        action="kb.create",
        resource_type="knowledge_base",
        resource_id=knowledge_base.id,
        details={"name": knowledge_base.name},
    )
    return KnowledgeBaseRead.model_validate(knowledge_base)


@router.post("/from-download", response_model=KnowledgeBaseWithDocumentResponse, status_code=status.HTTP_201_CREATED)
def create_knowledge_base_from_download(
    payload: KnowledgeBaseFromDownloadRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
    kb_service: KnowledgeBaseService = Depends(get_kb_service),
    document_service: DocumentService = Depends(get_document_service),
    alist_service: AListService = Depends(get_alist_service),
    operation_log_service: OperationLogService = Depends(get_operation_log_service),
    hot_question_cache=Depends(get_hot_question_cache),
    dispatch_document_processing=Depends(get_document_task_dispatcher),
) -> KnowledgeBaseWithDocumentResponse:
    file_path = alist_service.get_local_download_path(payload.task_id)
    knowledge_base = kb_service.create(
        session,
        user_id=current_user.id,
        payload=KnowledgeBaseCreate(
            name=payload.name,
            description=payload.description or f"由县志文件 {file_path.name} 创建",
        ),
    )
    document = document_service.create_from_local_file(
        session,
        user_id=current_user.id,
        kb_id=knowledge_base.id,
        source_path=file_path,
        content_type=mimetypes.guess_type(file_path.name)[0],
    )

    try:
        dispatch_document_processing(document.id)
    except Exception:
        logger.exception("文档异步处理任务投递失败。document_id=%s", document.id)

    operation_log_service.record(
        session,
        user_id=current_user.id,
        action="kb.create_from_download",
        resource_type="knowledge_base",
        resource_id=knowledge_base.id,
        details={"document_id": document.id, "filename": document.filename, "task_id": payload.task_id},
    )
    hot_question_cache.invalidate_scope(
        scope_key=build_hot_question_scope_key(user_id=current_user.id, kb_id=knowledge_base.id)
    )
    return KnowledgeBaseWithDocumentResponse(
        knowledge_base=KnowledgeBaseRead.model_validate(knowledge_base),
        document=DocumentRead.model_validate(document),
    )


@router.get("", response_model=list[KnowledgeBaseRead])
def list_knowledge_bases(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
    kb_service: KnowledgeBaseService = Depends(get_kb_service),
) -> list[KnowledgeBaseRead]:
    return [KnowledgeBaseRead.model_validate(item) for item in kb_service.list_for_user(session, user_id=current_user.id)]


@router.get("/{kb_id}", response_model=KnowledgeBaseRead)
def get_knowledge_base(
    kb_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
    kb_service: KnowledgeBaseService = Depends(get_kb_service),
) -> KnowledgeBaseRead:
    knowledge_base = kb_service.get_for_user(session, user_id=current_user.id, kb_id=kb_id)
    return KnowledgeBaseRead.model_validate(knowledge_base)


@router.put("/{kb_id}", response_model=KnowledgeBaseRead)
def update_knowledge_base(
    kb_id: int,
    payload: KnowledgeBaseUpdate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
    kb_service: KnowledgeBaseService = Depends(get_kb_service),
    operation_log_service: OperationLogService = Depends(get_operation_log_service),
) -> KnowledgeBaseRead:
    knowledge_base = kb_service.update(session, user_id=current_user.id, kb_id=kb_id, payload=payload)
    operation_log_service.record(
        session,
        user_id=current_user.id,
        action="kb.update",
        resource_type="knowledge_base",
        resource_id=knowledge_base.id,
        details={"name": knowledge_base.name},
    )
    return KnowledgeBaseRead.model_validate(knowledge_base)


@router.delete("/{kb_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_knowledge_base(
    kb_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
    kb_service: KnowledgeBaseService = Depends(get_kb_service),
    operation_log_service: OperationLogService = Depends(get_operation_log_service),
) -> Response:
    kb_service.delete(session, user_id=current_user.id, kb_id=kb_id)
    operation_log_service.record(
        session,
        user_id=current_user.id,
        action="kb.delete",
        resource_type="knowledge_base",
        resource_id=kb_id,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
