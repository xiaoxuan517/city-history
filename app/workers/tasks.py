from __future__ import annotations

import logging

from app.db.models.document import Document
from app.db.session import get_session_factory
from app.services.document_service import DocumentService
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="documents.process")
def process_document_task(document_id: int) -> dict[str, int | str]:
    session_factory = get_session_factory()
    session = session_factory()
    try:
        document = session.get(Document, document_id)
        if document is None:
            logger.warning("异步文档处理跳过，文档不存在。document_id=%s", document_id)
            return {"document_id": document_id, "status": "missing", "chunk_count": 0}

        processed_document, chunk_count = DocumentService().process_sync(
            session,
            user_id=document.user_id,
            document_id=document.id,
        )
        return {
            "document_id": processed_document.id,
            "status": processed_document.status.value,
            "chunk_count": chunk_count,
        }
    finally:
        session.close()


def enqueue_document_processing(document_id: int) -> str:
    result = process_document_task.delay(document_id)
    return str(result.id)


def get_document_task_dispatcher():
    return enqueue_document_processing
