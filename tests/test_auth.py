from __future__ import annotations

from app.security.auth import (
    create_session_token,
    hash_password,
    read_session_token,
    validate_password_strength,
    verify_password,
)


def test_password_hash_verification_roundtrip() -> None:
    encoded = hash_password("correct horse battery staple")

    assert verify_password("correct horse battery staple", encoded) is True
    assert verify_password("wrong password", encoded) is False


def test_signed_session_token_roundtrip_and_tamper_rejection() -> None:
    token = create_session_token(42)

    assert read_session_token(token) == 42
    assert read_session_token(f"{token}tampered") is None


def test_password_strength_requires_long_mixed_password() -> None:
    assert validate_password_strength("short") is not None
    assert validate_password_strength("long-but-missing-number") is not None
    assert validate_password_strength("GoodPassphrase42!") is None
