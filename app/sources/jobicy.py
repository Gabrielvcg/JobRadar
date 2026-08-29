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


class JobicyJobSource:
    name = "jobicy"

    def __init__(self, settings: dict[str, Any]) -> None:
        self.enabled = bool(settings.get("enabled", True))
        self.base_url: str | None = str(
            settings.get("base_url", "https://jobicy.com/api/v2/remote-jobs")
        )
        self.timeout_seconds = float(
            settings.get("timeout_seconds", get_settings().http_timeout_seconds)
        )
        self.retries = int(settings.get("retries", 2))
        self.min_interval_minutes = int(settings.get("min_interval_minutes", 360))
        self.minimum_score = int(settings.get("minimum_score", 35))
        self.count = int(settings.get("count", 50))
        self.rate_limit_seconds = float(settings.get("rate_limit_seconds", 2))
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
            for index, params in enumerate(request_list):
                payload = await self._fetch_payload(client, params)
                for item in _job_items(payload):
                    job = self._to_raw_job(item)
                    job_key = job.source_job_id or job.url or f"{job.company_name}:{job.title}"
                    jobs_by_id[job_key] = job
                if index < len(request_list) - 1:
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
        self, client: httpx.AsyncClient, request_params: dict[str, str]
    ) -> dict[str, Any]:
        params = {"count": str(self.count), **request_params}
        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                response = await client.get(str(self.base_url), params=params)
                if response.status_code == httpx.codes.TOO_MANY_REQUESTS:
                    await asyncio.sleep(_retry_after(response, attempt))
                    continue
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, dict):
                    msg = "Jobicy API returned a non-object JSON payload"
                    raise ValueError(msg)
                return payload
            except (httpx.HTTPError, ValueError) as exc:
                last_error = exc
                wait_seconds = min(2**attempt, 8)
                logger.warning(
                    "Fallo temporal consultando Jobicy",
                    extra={"source": self.name, "attempt": attempt + 1},
                )
                await asyncio.sleep(wait_seconds)
        raise RuntimeError(f"Jobicy API failed after retries: {last_error}") from last_error

    def _to_raw_job(self, item: dict[str, Any]) -> RawJob:
        industries = _string_list(item.get("jobIndustry", []))
        job_types = _string_list(item.get("jobType", []))
        level = _optional_str(item.get("jobLevel"))
        location = _optional_str(item.get("jobGeo"))
        requirements = [*industries, *job_types]
        if level:
            requirements.append(level)
        return RawJob(
            source_name=self.name,
            source_job_id=_optional_str(item.get("id")),
            company_name=str(item.get("companyName") or "Unknown company"),
            title=str(item.get("jobTitle") or "Untitled job"),
            description=str(item.get("jobDescription") or item.get("jobExcerpt") or ""),
            requirements=", ".join(requirements) or None,
            location=location,
            country=location,
            remote_type=RemoteType.REMOTE,
            employment_type=", ".join(job_types) or None,
            salary_original_text=_salary_text(item),
            url=_optional_str(item.get("url")),
            publication_date=_parse_datetime(item.get("pubDate")),
            raw_payload=dict(item),
        )


def _default_requests() -> list[dict[str, str]]:
    return [
        {"geo": "europe", "industry": "engineering"},
        {"geo": "europe", "industry": "dev"},
        {"geo": "europe", "industry": "admin"},
        {"geo": "europe", "industry": "cybersecurity"},
        {"geo": "spain", "industry": "engineering"},
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
    salary_min = _positive_int(item.get("salaryMin"))
    salary_max = _positive_int(item.get("salaryMax"))
    if salary_min is None and salary_max is None:
        return None
    currency = _optional_str(item.get("salaryCurrency"))
    period = _optional_str(item.get("salaryPeriod"))
    if salary_min is None:
        salary_range = str(salary_max)
    elif salary_max is None or salary_max == salary_min:
        salary_range = str(salary_min)
    else:
        salary_range = f"{salary_min}-{salary_max}"
    return " ".join(part for part in (salary_range, currency, period) if part)


def _parse_datetime(value: object) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(UTC)
    except ValueError:
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


def _contains_keyword(text: str, keyword: str) -> bool:
    normalized = keyword.strip().lower()
    if not normalized:
        return False
    escaped = re.escape(normalized).replace(r"\ ", r"\s+")
    return re.search(rf"(?<!\w){escaped}(?!\w)", text, re.IGNORECASE) is not None


def _retry_after(response: httpx.Response, attempt: int) -> float:
    value = response.headers.get("Retry-After")
    if value:
        try:
            return float(value)
        except ValueError:
            pass
    return min(5 * (attempt + 1), 30)
