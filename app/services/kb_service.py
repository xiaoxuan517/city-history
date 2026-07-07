from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.knowledge_base import KnowledgeBase
from app.schemas.knowledge_base import KnowledgeBaseCreate, KnowledgeBaseUpdate


class KnowledgeBaseNotFoundError(ValueError):
    pass


class KnowledgeBaseService:
    def create(self, session: Session, *, user_id: int, payload: KnowledgeBaseCreate) -> KnowledgeBase:
        knowledge_base = KnowledgeBase(
            user_id=user_id,
            name=payload.name.strip(),
            description=payload.description.strip() if payload.description else None,
        )
        session.add(knowledge_base)
        session.commit()
        session.refresh(knowledge_base)
        return knowledge_base

    def list_for_user(self, session: Session, *, user_id: int) -> list[KnowledgeBase]:
        statement = select(KnowledgeBase).where(KnowledgeBase.user_id == user_id).order_by(KnowledgeBase.created_at.desc())
        return list(session.scalars(statement))

    def get_for_user(self, session: Session, *, user_id: int, kb_id: int) -> KnowledgeBase:
        statement = select(KnowledgeBase).where(KnowledgeBase.id == kb_id, KnowledgeBase.user_id == user_id)
        knowledge_base = session.scalar(statement)
        if knowledge_base is None:
            raise KnowledgeBaseNotFoundError("Knowledge base not found")
        return knowledge_base

    def update(
        self,
        session: Session,
        *,
        user_id: int,
        kb_id: int,
        payload: KnowledgeBaseUpdate,
    ) -> KnowledgeBase:
        knowledge_base = self.get_for_user(session, user_id=user_id, kb_id=kb_id)
        if payload.name is not None:
            knowledge_base.name = payload.name.strip()
        if payload.description is not None:
            knowledge_base.description = payload.description.strip() or None
        session.commit()
        session.refresh(knowledge_base)
        return knowledge_base

    def delete(self, session: Session, *, user_id: int, kb_id: int) -> None:
        knowledge_base = self.get_for_user(session, user_id=user_id, kb_id=kb_id)
        session.delete(knowledge_base)
        session.commit()


def get_kb_service() -> KnowledgeBaseService:
    return KnowledgeBaseService()
