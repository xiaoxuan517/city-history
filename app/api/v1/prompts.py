from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.errors import ApiError
from app.api.v1.auth import get_current_user
from app.db.models.user import User
from app.db.session import get_db_session
from app.schemas.prompt import PromptVersionCreate, PromptVersionRead
from app.services.operation_log_service import OperationLogService, get_operation_log_service
from app.services.prompt_version_service import (
    PromptVersionConflictError,
    PromptVersionNotFoundError,
    PromptVersionService,
    get_prompt_version_service,
)

router = APIRouter(prefix="/api/v1/prompts", tags=["prompts"])


@router.get("", response_model=list[PromptVersionRead])
def list_prompt_versions(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
    prompt_version_service: PromptVersionService = Depends(get_prompt_version_service),
) -> list[PromptVersionRead]:
    _ = current_user
    return [PromptVersionRead.model_validate(item) for item in prompt_version_service.list_versions(session)]


@router.post("", response_model=PromptVersionRead, status_code=status.HTTP_201_CREATED)
def create_prompt_version(
    payload: PromptVersionCreate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
    prompt_version_service: PromptVersionService = Depends(get_prompt_version_service),
    operation_log_service: OperationLogService = Depends(get_operation_log_service),
) -> PromptVersionRead:
    try:
        prompt_version = prompt_version_service.create(session, payload)
    except PromptVersionConflictError as exc:
        raise ApiError(
            status_code=status.HTTP_409_CONFLICT,
            code="prompt_version_conflict",
            message=str(exc),
        ) from exc

    operation_log_service.record(
        session,
        user_id=current_user.id,
        action="prompt.create",
        resource_type="prompt_version",
        resource_id=prompt_version.id,
        details={"name": prompt_version.name, "version": prompt_version.version},
    )
    return PromptVersionRead.model_validate(prompt_version)


@router.post("/{prompt_version_id}/activate", response_model=PromptVersionRead)
def activate_prompt_version(
    prompt_version_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
    prompt_version_service: PromptVersionService = Depends(get_prompt_version_service),
    operation_log_service: OperationLogService = Depends(get_operation_log_service),
) -> PromptVersionRead:
    return _activate_prompt_version(
        prompt_version_id=prompt_version_id,
        current_user=current_user,
        session=session,
        prompt_version_service=prompt_version_service,
        operation_log_service=operation_log_service,
        action="prompt.activate",
    )


@router.post("/{prompt_version_id}/rollback", response_model=PromptVersionRead)
def rollback_prompt_version(
    prompt_version_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
    prompt_version_service: PromptVersionService = Depends(get_prompt_version_service),
    operation_log_service: OperationLogService = Depends(get_operation_log_service),
) -> PromptVersionRead:
    return _activate_prompt_version(
        prompt_version_id=prompt_version_id,
        current_user=current_user,
        session=session,
        prompt_version_service=prompt_version_service,
        operation_log_service=operation_log_service,
        action="prompt.rollback",
    )


def _activate_prompt_version(
    *,
    prompt_version_id: int,
    current_user: User,
    session: Session,
    prompt_version_service: PromptVersionService,
    operation_log_service: OperationLogService,
    action: str,
) -> PromptVersionRead:
    try:
        prompt_version = prompt_version_service.activate(session, prompt_version_id)
    except PromptVersionNotFoundError as exc:
        raise ApiError(
            status_code=status.HTTP_404_NOT_FOUND,
            code="prompt_version_not_found",
            message=str(exc),
        ) from exc

    operation_log_service.record(
        session,
        user_id=current_user.id,
        action=action,
        resource_type="prompt_version",
        resource_id=prompt_version.id,
        details={"name": prompt_version.name, "version": prompt_version.version},
    )
    return PromptVersionRead.model_validate(prompt_version)
