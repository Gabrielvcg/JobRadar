"""Expiry-aware evidence of a listing and its application path."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from app.scoring.text import canonical_url

VERIFICATION_KEY = "_jobradar_verification"
VERIFICATION_TTL = timedelta(hours=24)


def current_verification(
    payload: dict[str, Any],
    url: str | None,
    now: datetime | None = None,
) -> dict[str, Any]:
    value = payload.get(VERIFICATION_KEY)
    if not isinstance(value, dict) or canonical_url(value.get("listing_url")) != canonical_url(url):
        return {"state": "unverified", "reason": "Application availability has not been checked"}
    try:
        checked = datetime.fromisoformat(str(value["checked_at"]))
        checked = checked.replace(tzinfo=UTC) if checked.tzinfo is None else checked
    except (KeyError, ValueError):
        return {"state": "unverified", "reason": "Verification timestamp is unavailable"}
    age = (now or datetime.now(UTC)) - checked
    if age < timedelta(0) or age > VERIFICATION_TTL:
        return {**value, "state": "unverified", "reason": "Previous verification has expired"}
    return dict(value)
