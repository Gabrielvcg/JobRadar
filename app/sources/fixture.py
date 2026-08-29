from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from app.models.enums import RemoteType
from app.sources.base import RawJob, SearchConfig


class FixtureJobSource:
    name = "fixtures"

    def __init__(self, settings: dict[str, Any]) -> None:
        self.enabled = bool(settings.get("enabled", True))
        self.path = Path(str(settings.get("path", "fixtures/jobs.json")))
        self.base_url: str | None = str(settings.get("base_url", f"file://{self.path}"))
        self.min_interval_minutes = int(settings.get("min_interval_minutes", 0))
        self.minimum_score = int(settings.get("minimum_score", 0))

    async def fetch_jobs(self, search_config: SearchConfig) -> list[RawJob]:
        del search_config
        path = self.path if self.path.is_absolute() else Path.cwd() / self.path
        with path.open("r", encoding="utf-8") as file:
            payload = json.load(file)
        if not isinstance(payload, list):
            msg = "Fixture job file must contain a JSON array"
            raise ValueError(msg)
        return [self._to_raw_job(item) for item in payload]

    def _to_raw_job(self, item: dict[str, Any]) -> RawJob:
        return RawJob(
            source_name=self.name,
            source_job_id=_optional_str(item.get("source_job_id")),
            company_name=str(item.get("company_name") or "Unknown company"),
            company_website=_optional_str(item.get("company_website")),
            title=str(item.get("title") or "Untitled job"),
            description=str(item.get("description") or ""),
            requirements=_optional_str(item.get("requirements")),
            location=_optional_str(item.get("location")),
            country=_optional_str(item.get("country")),
            remote_type=_remote_type(item.get("remote_type")),
            employment_type=_optional_str(item.get("employment_type")),
            salary_original_text=_optional_str(item.get("salary_original_text")),
            url=_optional_str(item.get("url")),
            publication_date=_parse_datetime(item.get("publication_date")),
            expiration_date=_parse_datetime(item.get("expiration_date")),
            raw_payload=dict(item),
        )


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _parse_datetime(value: object) -> datetime | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def _remote_type(value: object) -> RemoteType:
    try:
        return RemoteType(str(value))
    except ValueError:
        return RemoteType.UNKNOWN
