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


class HimalayasJobSource:
    name = "himalayas"

    def __init__(self, settings: dict[str, Any]) -> None:
        self.enabled = bool(settings.get("enabled", True))
        self.base_url: str | None = str(
            settings.get("base_url", "https://himalayas.app/jobs/api/search")
        )
        self.timeout_seconds = float(
            settings.get("timeout_seconds", get_settings().http_timeout_seconds)
        )
        self.retries = int(settings.get("retries", 2))
        self.min_interval_minutes = int(settings.get("min_interval_minutes", 360))
        self.minimum_score = int(settings.get("minimum_score", 35))
        self.rate_limit_seconds = float(settings.get("rate_limit_seconds", 1))
        self.max_pages = int(settings.get("max_pages", 1))
        self.requests = _request_settings(settings.get("requests", []))
        self.must_have_any_keywords = _string_list(settings.get("must_have_any_keywords", []))
        self.required_any_keywords = _string_list(settings.get("required_any_keywords", []))
        self.title_required_any_keywords = _string_list(
            settings.get("title_required_any_keywords", [])
        )
        self.excluded_keywords = _string_list(settings.get("excluded_keywords", []))
        self.allowed_location_keywords = _string_list(
            settings.get("allowed_location_keywords", [])
        )

    async def fetch_jobs(self, search_config: SearchConfig) -> list[RawJob]:
        headers = {
            "Accept": "application/json",
            "User-Agent": "JobRadar/0.1 (personal job research; source attribution kept)",
        }
        jobs_by_id: dict[str, RawJob] = {}
        request_list = self.requests or _default_requests()
        async with httpx.AsyncClient(
            timeout=self.timeout_seconds, headers=headers, follow_redirects=True
        ) as client:
            for request_index, params in enumerate(request_list):
                for page in range(1, self.max_pages + 1):
                    payload = await self._fetch_payload(client, params, page)
                    items = _job_items(payload)
                    for item in items:
                        job = self._to_raw_job(item)
                        job_key = job.source_job_id or job.url or f"{job.company_name}:{job.title}"
                        jobs_by_id[job_key] = job
                    if page < self.max_pages:
                        await asyncio.sleep(self.rate_limit_seconds)
                if request_index < len(request_list) - 1:
                    await asyncio.sleep(self.rate_limit_seconds)
        return [
            job
            for job in jobs_by_id.values()
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

    async def _fetch_payload(
        self, client: httpx.AsyncClient, request_params: dict[str, str], page: int
    ) -> dict[str, Any]:
        params = {"sort": "recent", "page": str(page), **request_params}
        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                response = await client.get(str(self.base_url), params=params)
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, dict):
                    msg = "Himalayas API returned a non-object JSON payload"
                    raise ValueError(msg)
                return payload
            except (httpx.HTTPError, ValueError) as exc:
                last_error = exc
                wait_seconds = min(2**attempt, 8)
                logger.warning(
                    "Fallo temporal consultando Himalayas",
                    extra={"source": self.name, "attempt": attempt + 1},
                )
                await asyncio.sleep(wait_seconds)
        raise RuntimeError(f"Himalayas API failed after retries: {last_error}") from last_error

    def _to_raw_job(self, item: dict[str, Any]) -> RawJob:
        restrictions = _string_list(item.get("locationRestrictions", []))
        categories = _string_list(item.get("categories", []))
        seniority = _string_list(item.get("seniority", []))
        location = _bounded_text(", ".join(restrictions) or "Worldwide", 500)
        requirements = ", ".join([*categories, *seniority]) or None
        return RawJob(
            source_name=self.name,
            source_job_id=_optional_str(item.get("guid"))
            or _optional_str(item.get("applicationLink")),
            company_name=str(item.get("companyName") or "Unknown company"),
            title=str(item.get("title") or "Untitled job"),
            description=str(item.get("description") or item.get("excerpt") or ""),
            requirements=requirements,
            location=location,
            country=_country_from_location(location),
            remote_type=RemoteType.REMOTE,
            employment_type=_optional_str(item.get("employmentType")),
            salary_original_text=_salary_text(item),
            url=_optional_str(item.get("applicationLink")),
            publication_date=_timestamp_to_datetime(item.get("pubDate")),
            expiration_date=_timestamp_to_datetime(item.get("expiryDate")),
            raw_payload=dict(item),
        )


def _default_requests() -> list[dict[str, str]]:
    return [
        {"q": "java", "country": "Spain"},
        {"q": "spring", "country": "Spain"},
        {"q": "kotlin", "country": "Spain"},
        {"q": "java", "worldwide": "true"},
        {"q": "spring", "worldwide": "true"},
        {"q": "kotlin", "worldwide": "true"},
    ]


def _job_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    jobs = payload.get("jobs", [])
    if not isinstance(jobs, list):
        return []
    return [item for item in jobs if isinstance(item, dict)]


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
    salary_min = _positive_int(item.get("minSalary"))
    salary_max = _positive_int(item.get("maxSalary"))
    if salary_min is None and salary_max is None:
        return None
    currency = _optional_str(item.get("currency"))
    period = _optional_str(item.get("salaryPeriod"))
    if salary_min is None:
        salary_range = str(salary_max)
    elif salary_max is None or salary_max == salary_min:
        salary_range = str(salary_min)
    else:
        salary_range = f"{salary_min}-{salary_max}"
    return " ".join(part for part in (salary_range, currency, period) if part)


def _timestamp_to_datetime(value: object) -> datetime | None:
    if value is None or not isinstance(value, (str, bytes, int, float)):
        return None
    try:
        return datetime.fromtimestamp(int(value), tz=UTC)
    except (TypeError, ValueError, OSError):
        return None


def _positive_int(value: object) -> int | None:
    if value is None or not isinstance(value, (str, bytes, int, float)):
        return None
    try:
        number = int(value)
    except ValueError:
        return None
    return number if number > 0 else None


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _request_settings(value: object) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    requests = []
    for item in value:
        if isinstance(item, dict):
            requests.append({str(key): str(val) for key, val in item.items() if val is not None})
    return requests


def _country_from_location(location: str | None) -> str | None:
    if not location:
        return None
    location_lower = location.lower()
    if "worldwide" in location_lower:
        return "Worldwide"
    if "spain" in location_lower and len(location) <= 120:
        return "Spain"
    if "europe" in location_lower or _looks_like_european_region(location_lower):
        return "Europe"
    return None


def _looks_like_european_region(location_lower: str) -> bool:
    european_terms = {
        "austria",
        "belgium",
        "bulgaria",
        "croatia",
        "cyprus",
        "czechia",
        "denmark",
        "estonia",
        "finland",
        "france",
        "germany",
        "greece",
        "hungary",
        "ireland",
        "italy",
        "latvia",
        "lithuania",
        "luxembourg",
        "netherlands",
        "poland",
        "portugal",
        "romania",
        "slovakia",
        "slovenia",
        "spain",
        "sweden",
    }
    matches = sum(term in location_lower for term in european_terms)
    return matches >= 3


def _bounded_text(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[: limit - 1].rstrip() + "..."


def _contains_keyword(text: str, keyword: str) -> bool:
    normalized = keyword.strip().lower()
    if not normalized:
        return False
    escaped = re.escape(normalized).replace(r"\ ", r"\s+")
    return re.search(rf"(?<!\w){escaped}(?!\w)", text, re.IGNORECASE) is not None
