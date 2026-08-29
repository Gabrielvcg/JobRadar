from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.job import User
from app.security.auth import hash_password, verify_password


class UserAlreadyExistsError(ValueError):
    """Raised when an email is already registered."""


class UserRepository:
    def create_user(
        self,
        session: Session,
        *,
        email: str,
        display_name: str | None,
        password: str,
        is_admin: bool = False,
    ) -> User:
        normalized_email = normalize_email(email)
        if self.get_by_email(session, normalized_email) is not None:
            raise UserAlreadyExistsError("Email is already registered")
        name = " ".join((display_name or "").split()) or normalized_email.split("@", 1)[0]
        user = User(
            email=normalized_email,
            display_name=name[:120],
            password_hash=hash_password(password),
            is_admin=is_admin,
        )
        session.add(user)
        session.flush()
        return user

    def authenticate(self, session: Session, *, email: str, password: str) -> User | None:
        user = self.get_by_email(session, email)
        if user is None or not user.is_active:
            return None
        if not verify_password(password, user.password_hash):
            return None
        return user

    def get_by_email(self, session: Session, email: str) -> User | None:
        normalized_email = normalize_email(email)
        return session.scalar(
            select(User).where(func.lower(User.email) == normalized_email.lower())
        )

    def touch_login(self, session: Session, user: User) -> None:
        user.last_login_at = datetime.now(UTC)
        session.flush()


def normalize_email(email: str) -> str:
    return " ".join(email.strip().lower().split())
