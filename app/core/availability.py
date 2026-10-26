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
    if not isinstance(value, dict):
        return {"state": "unverified", "reason": "Application availability has not been checked"}
    malformed = {"state": "unverified", "reason": "Verification metadata is malformed"}
    if not isinstance(value.get("state"), str):
        return malformed
    listing_url = value.get("listing_url")
    if (listing_url is not None and not isinstance(listing_url, str)) or (
        url is not None and not isinstance(url, str)
    ):
        return malformed
    try:
        if canonical_url(listing_url) != canonical_url(url):
            return {
                "state": "unverified", "reason": "Application availability has not been checked",
            }
        # Only active proofs expose this optional field through the typed API contract.
        application_url = value.get("application_url")
        if value["state"] == "active" and application_url is not None:
            if not isinstance(application_url, str):
                return malformed
            canonical_url(application_url)
    except ValueError:
        return malformed
    try:
        checked = datetime.fromisoformat(str(value["checked_at"]))
        checked = checked.replace(tzinfo=UTC) if checked.tzinfo is None else checked
    except (KeyError, ValueError):
        return {"state": "unverified", "reason": "Verification timestamp is unavailable"}
    age = (now or datetime.now(UTC)) - checked
    if age < timedelta(0) or age > VERIFICATION_TTL:
        return {**value, "state": "unverified", "reason": "Previous verification has expired"}
    return dict(value)
