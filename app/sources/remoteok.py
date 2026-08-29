from __future__ import annotations

import asyncio
import logging
import re
from datetime import UTC, datetime
from typing import Any

import httpx

from app.core.config import get_settings
from app.models.enums import RemoteType
from app.sources.base import RawJob, SearchConfig

logger = logging.getLogger(__name__)


class RemoteOkJobSource:
    name = "remoteok"

    def __init__(self, settings: dict[str, Any]) -> None:
        self.enabled = bool(settings.get("enabled", True))
        self.base_url: str | None = str(settings.get("base_url", "https://remoteok.com/api"))
        self.timeout_seconds = float(
            settings.get("timeout_seconds", get_settings().http_timeout_seconds)
        )
        self.retries = int(settings.get("retries", 2))
        self.min_interval_minutes = int(settings.get("min_interval_minutes", 360))
        self.minimum_score = int(settings.get("minimum_score", 45))
        self.must_have_any_keywords = _string_list(settings.get("must_have_any_keywords", []))
        self.required_any_keywords = _string_list(settings.get("required_any_keywords", []))
        self.title_required_any_keywords = _string_list(
            settings.get("title_required_any_keywords", [])
        )
        self.excluded_keywords = _string_list(settings.get("excluded_keywords", []))
        self.allowed_location_keywords = _string_list(
            settings.get("allowed_location_keywords", [])
        )
        self.max_jobs = int(settings.get("max_jobs", 200))

    async def fetch_jobs(self, search_config: SearchConfig) -> list[RawJob]:
        headers = {
            "Accept": "application/json",
            "User-Agent": "JobRadar/0.1 (personal job research; source attribution kept)",
        }
        async with httpx.AsyncClient(timeout=self.timeout_seconds, headers=headers) as client:
            payload = await self._fetch_payload(client)
        raw_jobs = [self._to_raw_job(item) for item in _job_items(payload)]
        return [
            job
            for job in raw_jobs[: self.max_jobs]
            if _matches_affinity(
                job,
                search_config.queries,
                self.required_any_keywords,
                self.title_required_any_keywords,
                self.excluded_keywords,
                self.allowed_location_keywords,
                self.must_have_any_keywords,
            )
        ]

    async def _fetch_payload(self, client: httpx.AsyncClient) -> list[dict[str, Any]]:
        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                response = await client.get(str(self.base_url))
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, list):
                    msg = "Remote OK API returned a non-list JSON payload"
                    raise ValueError(msg)
                return [item for item in payload if isinstance(item, dict)]
            except (httpx.HTTPError, ValueError) as exc:
                last_error = exc
                wait_seconds = min(2**attempt, 8)
                logger.warning(
                    "Fallo temporal consultando Remote OK",
                    extra={"source": self.name, "attempt": attempt + 1},
                )
                await asyncio.sleep(wait_seconds)
        raise RuntimeError(f"Remote OK API failed after retries: {last_error}") from last_error

    def _to_raw_job(self, item: dict[str, Any]) -> RawJob:
        tags = _string_list(item.get("tags", []))
        location = _optional_str(item.get("location"))
        return RawJob(
            source_name=self.name,
            source_job_id=_optional_str(item.get("id")),
            company_name=str(item.get("company") or "Unknown company"),
            company_website=_optional_str(item.get("company_url")),
            title=str(item.get("position") or "Untitled job"),
            description=str(item.get("description") or ""),
            requirements=", ".join(tags) or None,
            location=location,
            country=_country_from_location(location),
            remote_type=RemoteType.REMOTE,
            employment_type=_optional_str(item.get("job_type")),
            salary_original_text=_salary_text(item),
            url=_optional_str(item.get("url")),
            publication_date=_parse_datetime(item.get("date")),
            raw_payload=dict(item),
        )


def _job_items(payload: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [item for item in payload if "legal" not in item and item.get("id")]


def _matches_affinity(
    job: RawJob,
    queries: list[str],
    required_any_keywords: list[str],
    title_required_any_keywords: list[str],
    excluded_keywords: list[str],
    allowed_location_keywords: list[str],
    must_have_any_keywords: list[str] | None = None,
) -> bool:
    title = job.title.lower()
    location = (job.location or "").lower()
    haystack = f"{job.title} {job.description} {job.requirements or ''}".lower()
    if allowed_location_keywords and location and not any(
        keyword.lower() in location for keyword in allowed_location_keywords
    ):
        return False
    if must_have_any_keywords and not any(
        _contains_keyword(haystack, keyword) for keyword in must_have_any_keywords
    ):
        return False
    if any(_contains_keyword(haystack, keyword) for keyword in excluded_keywords):
        return False
    if title_required_any_keywords and not any(
        _contains_keyword(title, keyword) for keyword in title_required_any_keywords
    ):
        return False
    if required_any_keywords:
        return any(_contains_keyword(haystack, keyword) for keyword in required_any_keywords)
    return any(_contains_keyword(haystack, query) for query in queries)


def _salary_text(item: dict[str, Any]) -> str | None:
    salary_min = _positive_int(item.get("salary_min"))
    salary_max = _positive_int(item.get("salary_max"))
    if salary_min is None and salary_max is None:
        return None
    if salary_min is None:
        return f"${salary_max}"
    if salary_max is None or salary_max == salary_min:
        return f"${salary_min}"
    return f"${salary_min} - ${salary_max}"


def _positive_int(value: object) -> int | None:
    if value is None or not isinstance(value, (str, bytes, int, float)):
        return None
    try:
        number = int(value)
    except ValueError:
        return None
    return number if number > 0 else None


def _parse_datetime(value: object) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).removesuffix("Z")).astimezone(UTC)
    except ValueError:
        return None


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _country_from_location(location: str | None) -> str | None:
    if not location:
        return None
    location_lower = location.lower()
    if any(token in location_lower for token in ("spain", "europe", "emea", "worldwide")):
        return location
    return None


def _contains_keyword(text: str, keyword: str) -> bool:
    normalized = keyword.strip().lower()
    if not normalized:
        return False
    escaped = re.escape(normalized).replace(r"\ ", r"\s+")
    return re.search(rf"(?<!\w){escaped}(?!\w)", text, re.IGNORECASE) is not None
