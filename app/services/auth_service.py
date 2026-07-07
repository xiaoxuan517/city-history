from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password, verify_password
from app.db.models.user import User
from app.schemas.auth import TokenResponse, UserCreate, UserRead


class AuthError(ValueError):
    pass


class AuthService:
    def get_user_by_id(self, session: Session, user_id: int) -> User | None:
        return session.get(User, user_id)

    def get_user_by_username_or_email(self, session: Session, value: str) -> User | None:
        normalized = value.strip().lower()
        statement = select(User).where(
            or_(
                User.username == normalized,
                User.email == normalized,
            )
        )
        return session.scalar(statement)

    def register(self, session: Session, payload: UserCreate) -> User:
        username = payload.username.strip().lower()
        email = payload.email.strip().lower()
        existing = session.scalar(select(User).where(or_(User.username == username, User.email == email)))
        if existing is not None:
            raise AuthError("Username or email already exists")

        user = User(
            username=username,
            email=email,
            password_hash=hash_password(payload.password),
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        return user

    def login(self, session: Session, *, username_or_email: str, password: str) -> TokenResponse:
        user = self.get_user_by_username_or_email(session, username_or_email)
        if user is None or not verify_password(password, user.password_hash):
            raise AuthError("Invalid username/email or password")

        token = create_access_token(str(user.id))
        return TokenResponse(access_token=token, user=UserRead.model_validate(user))


def get_auth_service() -> AuthService:
    return AuthService()
