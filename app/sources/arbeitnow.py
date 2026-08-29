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


class ArbeitnowJobSource:
    name = "arbeitnow"

    def __init__(self, settings: dict[str, Any]) -> None:
        self.enabled = bool(settings.get("enabled", True))
        self.base_url: str | None = str(
            settings.get("base_url", "https://www.arbeitnow.com/api/job-board-api")
        )
        self.max_pages = int(settings.get("max_pages", 1))
        self.rate_limit_seconds = float(settings.get("rate_limit_seconds", 1))
        self.min_interval_minutes = int(settings.get("min_interval_minutes", 0))
        self.timeout_seconds = float(
            settings.get("timeout_seconds", get_settings().http_timeout_seconds)
        )
        self.retries = int(settings.get("retries", 2))
        self.minimum_score = int(settings.get("minimum_score", 50))
        self.strict_search_filter = bool(settings.get("strict_search_filter", False))
        self.must_have_any_keywords = _string_list(settings.get("must_have_any_keywords", []))
        self.required_any_keywords = _string_list(settings.get("required_any_keywords", []))
        self.title_required_any_keywords = _string_list(
            settings.get("title_required_any_keywords", [])
        )
        self.excluded_keywords = _string_list(settings.get("excluded_keywords", []))

    async def fetch_jobs(self, search_config: SearchConfig) -> list[RawJob]:
        headers = {
            "Accept": "application/json",
            "User-Agent": "JobRadar/0.1 (local personal job research; https://www.arbeitnow.com)",
        }
        jobs: list[RawJob] = []
        async with httpx.AsyncClient(timeout=self.timeout_seconds, headers=headers) as client:
            for page in range(1, self.max_pages + 1):
                payload = await self._fetch_page(client, page)
                jobs.extend(self._to_raw_jobs(payload, search_config))
                if page < self.max_pages:
                    await asyncio.sleep(self.rate_limit_seconds)
        return jobs

    async def _fetch_page(self, client: httpx.AsyncClient, page: int) -> dict[str, Any]:
        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                response = await client.get(str(self.base_url), params={"page": page})
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, dict):
                    msg = "Arbeitnow API returned a non-object JSON payload"
                    raise ValueError(msg)
                return payload
            except (httpx.HTTPError, ValueError) as exc:
                last_error = exc
                wait_seconds = min(2**attempt, 8)
                logger.warning(
                    "Fallo temporal consultando Arbeitnow",
                    extra={"source": self.name, "page": page, "attempt": attempt + 1},
                )
                await asyncio.sleep(wait_seconds)
        raise RuntimeError(f"Arbeitnow API failed after retries: {last_error}") from last_error

    def _to_raw_jobs(self, payload: dict[str, Any], search_config: SearchConfig) -> list[RawJob]:
        data = payload.get("data", [])
        if not isinstance(data, list):
            return []
        jobs = [self._to_raw_job(item) for item in data if isinstance(item, dict)]
        if not self.strict_search_filter:
            return jobs
        return [
            job
            for job in jobs
            if _matches_affinity(
                job,
                search_config.queries,
                self.required_any_keywords,
                self.title_required_any_keywords,
                self.excluded_keywords,
                self.must_have_any_keywords,
            )
        ]

    def _to_raw_job(self, item: dict[str, Any]) -> RawJob:
        slug = _optional_str(item.get("slug"))
        raw_tags = item.get("tags")
        raw_job_types = item.get("job_types")
        tags: list[Any] = raw_tags if isinstance(raw_tags, list) else []
        job_types: list[Any] = raw_job_types if isinstance(raw_job_types, list) else []
        location = _optional_str(item.get("location"))
        remote_type = RemoteType.REMOTE if bool(item.get("remote")) else RemoteType.UNKNOWN
        description = str(item.get("description") or "")
        requirements = ", ".join(str(tag) for tag in tags)
        employment_type = ", ".join(str(job_type) for job_type in job_types) or None
        return RawJob(
            source_name=self.name,
            source_job_id=slug,
            company_name=str(item.get("company_name") or "Unknown company"),
            title=str(item.get("title") or "Untitled job"),
            description=description,
            requirements=requirements or None,
            location=location,
            country=_country_from_location(location),
            remote_type=remote_type,
            employment_type=employment_type,
            url=_optional_str(item.get("url")) or _url_from_slug(slug),
            publication_date=_timestamp_to_datetime(item.get("created_at")),
            raw_payload=dict(item),
        )


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _timestamp_to_datetime(value: object) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, (str, bytes, int, float)):
        return None
    try:
        return datetime.fromtimestamp(int(value), tz=UTC)
    except (TypeError, ValueError, OSError):
        return None


def _url_from_slug(slug: str | None) -> str | None:
    if not slug:
        return None
    return f"https://www.arbeitnow.com/jobs/{slug}"


def _country_from_location(location: str | None) -> str | None:
    if not location:
        return None
    location_lower = location.lower()
    if "germany" in location_lower or "berlin" in location_lower or "munich" in location_lower:
        return "Germany"
    if "spain" in location_lower or "madrid" in location_lower or "barcelona" in location_lower:
        return "Spain"
    return None


def _matches_affinity(
    job: RawJob,
    queries: list[str],
    required_any_keywords: list[str],
    title_required_any_keywords: list[str],
    excluded_keywords: list[str],
    must_have_any_keywords: list[str] | None = None,
) -> bool:
    haystack = f"{job.title} {job.description} {job.requirements or ''}".lower()
    title = job.title.lower()
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


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _contains_keyword(text: str, keyword: str) -> bool:
    normalized = keyword.strip().lower()
    if not normalized:
        return False
    escaped = re.escape(normalized).replace(r"\ ", r"\s+")
    return re.search(rf"(?<!\w){escaped}(?!\w)", text, re.IGNORECASE) is not None
