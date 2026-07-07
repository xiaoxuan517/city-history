from __future__ import annotations

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.agent.prompts import BASE_SYSTEM_PROMPT
from app.db.models.prompt import PromptVersion
from app.schemas.prompt import PromptVersionCreate


DEFAULT_PROMPT_NAME = "default_rag_assistant"
DEFAULT_PROMPT_VERSION = "v1"


class PromptVersionNotFoundError(Exception):
    pass


class PromptVersionConflictError(Exception):
    pass


class PromptVersionService:
    def get_by_id(self, session: Session, prompt_version_id: int) -> PromptVersion:
        prompt_version = session.get(PromptVersion, prompt_version_id)
        if prompt_version is None:
            raise PromptVersionNotFoundError("Prompt version not found")
        return prompt_version

    def list_versions(self, session: Session) -> list[PromptVersion]:
        statement = select(PromptVersion).order_by(
            PromptVersion.is_active.desc(),
            PromptVersion.created_at.desc(),
            PromptVersion.id.desc(),
        )
        return list(session.scalars(statement))

    def create(self, session: Session, payload: PromptVersionCreate) -> PromptVersion:
        name = payload.name.strip()
        version = payload.version.strip()
        existing = session.scalar(
            select(PromptVersion).where(PromptVersion.name == name, PromptVersion.version == version)
        )
        if existing is not None:
            raise PromptVersionConflictError("Prompt version already exists")

        prompt_version = PromptVersion(
            name=name,
            version=version,
            description=payload.description,
            system_prompt=payload.system_prompt,
            is_active=False,
        )
        session.add(prompt_version)
        session.commit()
        session.refresh(prompt_version)
        return prompt_version

    def activate(self, session: Session, prompt_version_id: int) -> PromptVersion:
        prompt_version = self.get_by_id(session, prompt_version_id)

        session.execute(update(PromptVersion).values(is_active=False))
        prompt_version.is_active = True
        session.commit()
        session.refresh(prompt_version)
        return prompt_version

    def get_active(self, session: Session) -> PromptVersion:
        statement = (
            select(PromptVersion)
            .where(PromptVersion.is_active.is_(True))
            .order_by(PromptVersion.created_at.desc(), PromptVersion.id.desc())
        )
        active = session.scalar(statement)
        if active is not None:
            return active
        return self.ensure_default(session)

    def ensure_default(self, session: Session) -> PromptVersion:
        statement = select(PromptVersion).where(
            PromptVersion.name == DEFAULT_PROMPT_NAME,
            PromptVersion.version == DEFAULT_PROMPT_VERSION,
        )
        existing = session.scalar(statement)
        if existing is not None:
            if not existing.is_active:
                existing.is_active = True
                session.commit()
                session.refresh(existing)
            return existing

        prompt_version = PromptVersion(
            name=DEFAULT_PROMPT_NAME,
            version=DEFAULT_PROMPT_VERSION,
            description="Default RAG assistant prompt used by the built-in Agent.",
            system_prompt=BASE_SYSTEM_PROMPT,
            is_active=True,
        )
        session.add(prompt_version)
        session.commit()
        session.refresh(prompt_version)
        return prompt_version


def get_prompt_version_service() -> PromptVersionService:
    return PromptVersionService()
