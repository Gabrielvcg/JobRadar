from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import time

from fastapi import Request
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.job import User

SESSION_COOKIE_NAME = "jobradar_session"
SESSION_MAX_AGE_SECONDS = 60 * 60 * 24 * 60
PASSWORD_ALGORITHM = "pbkdf2_sha256"
PASSWORD_ITERATIONS = 260_000
MIN_PASSWORD_LENGTH = 14
PASSWORD_POLICY_MESSAGE = (
    "Password must be at least 14 characters and include lowercase, uppercase, "
    "number, and symbol characters."
)


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), PASSWORD_ITERATIONS
    ).hex()
    return f"{PASSWORD_ALGORITHM}${PASSWORD_ITERATIONS}${salt}${digest}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, iterations_text, salt, expected = encoded.split("$", 3)
        iterations = int(iterations_text)
    except ValueError:
        return False
    if algorithm != PASSWORD_ALGORITHM:
        return False
    actual = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), iterations
    ).hex()
    return hmac.compare_digest(actual, expected)


def validate_password_strength(password: str) -> str | None:
    if len(password) < MIN_PASSWORD_LENGTH:
        return PASSWORD_POLICY_MESSAGE
    checks = (
        any(character.islower() for character in password),
        any(character.isupper() for character in password),
        any(character.isdigit() for character in password),
        any(not character.isalnum() for character in password),
    )
    if not all(checks):
        return PASSWORD_POLICY_MESSAGE
    return None


def create_session_token(user_id: int) -> str:
    payload = f"{user_id}:{int(time.time())}:{secrets.token_urlsafe(12)}"
    payload_b64 = _urlsafe_b64encode(payload.encode("utf-8"))
    signature = _sign(payload_b64)
    return f"{payload_b64}.{signature}"


def read_session_token(token: str | None) -> int | None:
    if not token or "." not in token:
        return None
    payload_b64, signature = token.rsplit(".", 1)
    if not hmac.compare_digest(_sign(payload_b64), signature):
        return None
    try:
        payload = _urlsafe_b64decode(payload_b64).decode("utf-8")
        user_id_text, issued_at_text, _nonce = payload.split(":", 2)
        issued_at = int(issued_at_text)
        user_id = int(user_id_text)
    except (ValueError, UnicodeDecodeError):
        return None
    if issued_at + SESSION_MAX_AGE_SECONDS < int(time.time()):
        return None
    return user_id


def get_current_user(request: Request, session: Session) -> User | None:
    user_id = read_session_token(request.cookies.get(SESSION_COOKIE_NAME))
    if user_id is None:
        return None
    user = session.get(User, user_id)
    if user is None or not user.is_active:
        return None
    return user


def set_session_cookie(response: Response, user_id: int) -> None:
    token = create_session_token(user_id)
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=SESSION_MAX_AGE_SECONDS,
        httponly=True,
        secure=get_settings().session_cookie_secure,
        samesite="lax",
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE_NAME, path="/")


def _sign(payload_b64: str) -> str:
    secret = get_settings().app_secret_key.encode("utf-8")
    return hmac.new(secret, payload_b64.encode("utf-8"), hashlib.sha256).hexdigest()


def _urlsafe_b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _urlsafe_b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)
