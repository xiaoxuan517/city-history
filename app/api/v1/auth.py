from __future__ import annotations

from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.api.errors import ApiError
from app.core.security import decode_access_token
from app.db.models.user import User
from app.db.session import get_db_session
from app.schemas.auth import TokenResponse, UserCreate, UserLogin, UserRead
from app.services.auth_service import AuthError, AuthService, get_auth_service
from app.services.operation_log_service import OperationLogService, get_operation_log_service

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def get_current_user(
    token: str = Depends(oauth2_scheme),
    session: Session = Depends(get_db_session),
    auth_service: AuthService = Depends(get_auth_service),
) -> User:
    try:
        payload = decode_access_token(token)
        user_id = int(payload.get("sub", ""))
    except (TypeError, ValueError):
        raise ApiError(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="invalid_credentials",
            message="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = auth_service.get_user_by_id(session, user_id)
    if user is None:
        raise ApiError(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="invalid_credentials",
            message="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register(
    payload: UserCreate,
    session: Session = Depends(get_db_session),
    auth_service: AuthService = Depends(get_auth_service),
    operation_log_service: OperationLogService = Depends(get_operation_log_service),
) -> UserRead:
    try:
        user = auth_service.register(session, payload)
    except AuthError as exc:
        raise ApiError(
            status_code=status.HTTP_409_CONFLICT,
            code="auth_conflict",
            message=str(exc),
        ) from exc
    operation_log_service.record(
        session,
        user_id=user.id,
        action="auth.register",
        resource_type="user",
        resource_id=user.id,
        details={"username": user.username, "email": user.email},
    )
    return UserRead.model_validate(user)


@router.post("/login", response_model=TokenResponse)
def login(
    payload: UserLogin,
    session: Session = Depends(get_db_session),
    auth_service: AuthService = Depends(get_auth_service),
    operation_log_service: OperationLogService = Depends(get_operation_log_service),
) -> TokenResponse:
    try:
        token_response = auth_service.login(
            session,
            username_or_email=payload.username_or_email,
            password=payload.password,
        )
    except AuthError as exc:
        raise ApiError(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="invalid_credentials",
            message=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    operation_log_service.record(
        session,
        user_id=token_response.user.id,
        action="auth.login",
        resource_type="user",
        resource_id=token_response.user.id,
        details={"username_or_email": payload.username_or_email.strip().lower()},
    )
    return token_response


@router.get("/me", response_model=UserRead)
def me(current_user: User = Depends(get_current_user)) -> UserRead:
    return UserRead.model_validate(current_user)
