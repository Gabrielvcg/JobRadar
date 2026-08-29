from __future__ import annotations

import asyncio
import logging
import os
import re
from datetime import datetime
from typing import Any

import httpx

from app.core.config import get_settings
from app.models.enums import RemoteType
from app.sources.base import RawJob, SearchConfig

logger = logging.getLogger(__name__)


class AdzunaJobSource:
    name = "adzuna"

    def __init__(self, settings: dict[str, Any]) -> None:
        self.enabled = bool(settings.get("enabled", True))
        self.base_url: str | None = str(
            settings.get("base_url", "https://api.adzuna.com/v1/api/jobs")
        )
        self.country = str(settings.get("country", "es"))
        self.app_id = _optional_str(settings.get("app_id")) or os.getenv("ADZUNA_APP_ID")
        self.app_key = _optional_str(settings.get("app_key")) or os.getenv("ADZUNA_APP_KEY")
        self.requests = _request_list(settings.get("requests", []))
        self.results_per_page = int(settings.get("results_per_page", 50))
        self.max_pages = int(settings.get("max_pages", 1))
        self.rate_limit_seconds = float(settings.get("rate_limit_seconds", 3))
        self.min_interval_minutes = int(settings.get("min_interval_minutes", 360))
        self.timeout_seconds = float(
            settings.get("timeout_seconds", get_settings().http_timeout_seconds)
        )
        self.retries = int(settings.get("retries", 2))
        self.minimum_score = int(settings.get("minimum_score", 35))
        self.strict_search_filter = bool(settings.get("strict_search_filter", True))
        self.required_any_keywords = _string_list(settings.get("required_any_keywords", []))
        self.title_required_any_keywords = _string_list(
            settings.get("title_required_any_keywords", [])
        )
        self.excluded_keywords = _string_list(settings.get("excluded_keywords", []))
        self.allowed_location_keywords = _string_list(
            settings.get("allowed_location_keywords", [])
        )

    async def fetch_jobs(self, search_config: SearchConfig) -> list[RawJob]:
        if not self.app_id or not self.app_key:
            logger.warning("Adzuna no tiene credenciales configuradas", extra={"source": self.name})
            return []
        headers = {
            "Accept": "application/json",
            "User-Agent": "JobRadar/0.1 (personal job research)",
        }
        jobs: list[RawJob] = []
        async with httpx.AsyncClient(timeout=self.timeout_seconds, headers=headers) as client:
            for request in self._requests(search_config):
                for page in range(1, self.max_pages + 1):
                    payload = await self._fetch_page(client, request, page)
                    jobs.extend(self._to_raw_jobs(payload, search_config))
                    await asyncio.sleep(self.rate_limit_seconds)
        return _dedupe_jobs(jobs)

    async def _fetch_page(
        self, client: httpx.AsyncClient, request: dict[str, str], page: int
    ) -> dict[str, Any]:
        url = f"{self.base_url}/{self.country}/search/{page}"
        params = {
            "app_id": self.app_id,
            "app_key": self.app_key,
            "content-type": "application/json",
            "results_per_page": self.results_per_page,
            **request,
        }
        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                response = await client.get(url, params=params)
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, dict):
                    msg = "Adzuna API returned a non-object JSON payload"
                    raise ValueError(msg)
                return payload
            except (httpx.HTTPError, ValueError) as exc:
                last_error = exc
                wait_seconds = min(2**attempt, 8)
                logger.warning(
                    "Fallo temporal consultando Adzuna",
                    extra={"source": self.name, "page": page, "attempt": attempt + 1},
                )
                await asyncio.sleep(wait_seconds)
        raise RuntimeError(f"Adzuna API failed after retries: {last_error}") from last_error

    def _requests(self, search_config: SearchConfig) -> list[dict[str, str]]:
        if self.requests:
            return self.requests
        cities = search_config.cities or [""]
        return [
            {"what": query, "where": city}
            for query in search_config.queries
            for city in cities
            if query
        ]

    def _to_raw_jobs(self, payload: dict[str, Any], search_config: SearchConfig) -> list[RawJob]:
        results = payload.get("results", [])
        if not isinstance(results, list):
            return []
        jobs = [self._to_raw_job(item) for item in results if isinstance(item, dict)]
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
                self.allowed_location_keywords,
            )
        ]

    def _to_raw_job(self, item: dict[str, Any]) -> RawJob:
        company = item.get("company")
        location = item.get("location")
        category = item.get("category")
        location_text = _display_name(location) or _area_location(location)
        salary_text = _salary_text(item)
        return RawJob(
            source_name=self.name,
            source_job_id=_optional_str(item.get("id")),
            company_name=_display_name(company) or "Unknown company",
            title=str(item.get("title") or "Untitled job"),
            description=str(item.get("description") or ""),
            requirements=", ".join(
                part
                for part in (
                    _display_name(category),
                    _optional_str(item.get("contract_time")),
                    _optional_str(item.get("contract_type")),
                )
                if part
            )
            or None,
            location=location_text,
            country="Spain" if self.country.lower() == "es" else None,
            remote_type=RemoteType.UNKNOWN,
            employment_type=_optional_str(item.get("contract_time")),
            salary_original_text=salary_text,
            url=_optional_str(item.get("redirect_url")),
            publication_date=_parse_datetime(item.get("created")),
            raw_payload=dict(item),
        )


def _matches_affinity(
    job: RawJob,
    queries: list[str],
    required_any_keywords: list[str],
    title_required_any_keywords: list[str],
    excluded_keywords: list[str],
    allowed_location_keywords: list[str],
) -> bool:
    haystack = f"{job.title} {job.description} {job.requirements or ''}".lower()
    title = job.title.lower()
    location = f"{job.location or ''} {job.country or ''}".lower()
    if any(_contains_keyword(haystack, keyword) for keyword in excluded_keywords):
        return False
    if title_required_any_keywords and not any(
        _contains_keyword(title, keyword) for keyword in title_required_any_keywords
    ):
        return False
    if allowed_location_keywords and not any(
        _contains_keyword(location, keyword) for keyword in allowed_location_keywords
    ):
        return False
    if required_any_keywords:
        return any(_contains_keyword(haystack, keyword) for keyword in required_any_keywords)
    return any(_contains_keyword(haystack, query) for query in queries)


def _request_list(value: object) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    requests: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        request = {
            str(key): str(request_value)
            for key, request_value in item.items()
            if request_value is not None and str(request_value).strip()
        }
        if request:
            requests.append(request)
    return requests


def _display_name(value: object) -> str | None:
    if not isinstance(value, dict):
        return None
    return _optional_str(value.get("display_name"))


def _area_location(value: object) -> str | None:
    if not isinstance(value, dict):
        return None
    area = value.get("area")
    if not isinstance(area, list):
        return None
    return ", ".join(str(part) for part in area if part)


def _salary_text(item: dict[str, Any]) -> str | None:
    salary_min = item.get("salary_min")
    salary_max = item.get("salary_max")
    if salary_min is None and salary_max is None:
        return None
    currency = _optional_str(item.get("salary_currency")) or "EUR"
    if salary_min is not None and salary_max is not None:
        return f"{salary_min}-{salary_max} {currency} annual"
    amount = salary_min if salary_min is not None else salary_max
    return f"{amount} {currency} annual"


def _parse_datetime(value: object) -> datetime | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def _dedupe_jobs(jobs: list[RawJob]) -> list[RawJob]:
    seen: set[str] = set()
    deduped: list[RawJob] = []
    for job in jobs:
        key = job.source_job_id or f"{job.company_name}|{job.title}|{job.location}|{job.url}"
        if key in seen:
            continue
        seen.add(key)
        deduped.append(job)
    return deduped


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


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
