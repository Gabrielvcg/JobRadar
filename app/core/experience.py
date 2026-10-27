"""Professional tenure at month precision; credentials never add employment time."""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo


def career_today() -> date:
    return datetime.now(ZoneInfo("Europe/Madrid")).date()


def professional_months(start_month: str, as_of: date | None = None) -> int:
    start = date.fromisoformat(f"{start_month}-01")
    today = as_of or career_today()
    return max(0, (today.year - start.year) * 12 + today.month - start.month)
