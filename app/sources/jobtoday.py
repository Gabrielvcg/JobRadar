from __future__ import annotations

import asyncio
import json
import logging
import re
import unicodedata
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from app.core.config import get_settings
from app.models.enums import RemoteType
from app.sources.base import RawJob, SearchConfig

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class JobTodayPage:
    url: str
    location_hint: str | None
    country: str | None


class JobTodayJobSource:
    name = "jobtoday"

    def __init__(self, settings: dict[str, Any]) -> None:
        self.enabled = bool(settings.get("enabled", True))
        self.base_url: str | None = str(settings.get("base_url", "https://jobtoday.com"))
        self.pages = _page_list(settings.get("pages", []))
        self.timeout_seconds = float(
            settings.get("timeout_seconds", get_settings().http_timeout_seconds)
        )
        self.retries = int(settings.get("retries", 2))
        self.rate_limit_seconds = float(settings.get("rate_limit_seconds", 1))
        self.min_interval_minutes = int(settings.get("min_interval_minutes", 360))
        self.minimum_score = int(settings.get("minimum_score", 50))
        self.max_jobs = int(settings.get("max_jobs", 40))
        self.internal_only = bool(settings.get("internal_only", True))
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
        headers = {
            "Accept": "text/html,application/xhtml+xml",
            "User-Agent": "JobRadar/0.1 (personal job research; source attribution kept)",
        }
        jobs: list[RawJob] = []
        async with httpx.AsyncClient(
            timeout=self.timeout_seconds, headers=headers, follow_redirects=True
        ) as client:
            for page in self.pages:
                try:
                    payload = await self._fetch_page(client, page)
                except RuntimeError:
                    logger.warning(
                        "No se pudo consultar la pagina de JobToday",
                        extra={"source": self.name, "url": page.url},
                    )
                    continue
                jobs.extend(self._jobs_from_html(payload, page))
                await asyncio.sleep(self.rate_limit_seconds)
        jobs = _dedupe_jobs(jobs)
        if not self.strict_search_filter:
            return jobs[: self.max_jobs]
        return [
            job
            for job in jobs[: self.max_jobs]
            if _matches_affinity(
                job,
                search_config.queries,
                self.required_any_keywords,
                self.title_required_any_keywords,
                self.excluded_keywords,
                self.allowed_location_keywords,
            )
        ]

    async def _fetch_page(self, client: httpx.AsyncClient, page: JobTodayPage) -> str:
        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                response = await client.get(page.url)
                response.raise_for_status()
                return response.text
            except httpx.HTTPError as exc:
                last_error = exc
                wait_seconds = min(2**attempt, 8)
                logger.warning(
                    "Fallo temporal consultando JobToday",
                    extra={"source": self.name, "url": page.url, "attempt": attempt + 1},
                )
                await asyncio.sleep(wait_seconds)
        raise RuntimeError(f"JobToday page failed after retries: {last_error}") from last_error

    def _jobs_from_html(self, payload: str, page: JobTodayPage) -> list[RawJob]:
        data = _next_data(payload)
        if data is None:
            return []
        jobs: list[RawJob] = []
        for item in _job_items(data):
            if self.internal_only and bool(item.get("isExternalJob")):
                continue
            job = self._to_raw_job(item, page)
            if job is not None:
                jobs.append(job)
        return jobs

    def _to_raw_job(self, item: dict[str, Any], page: JobTodayPage) -> RawJob | None:
        title = _optional_str(item.get("role"))
        source_job_id = _optional_str(item.get("key"))
        if title is None or source_job_id is None:
            return None
        canonical_url = _optional_str(item.get("canonicalUrl"))
        external_url = _optional_str(item.get("externalUrl"))
        url = urljoin(str(self.base_url), canonical_url) if canonical_url else external_url
        if url is None:
            return None
        description = _optional_str(item.get("descriptionDeMarkdown")) or _optional_str(
            item.get("description")
        )
        location = _location(item, page) or page.location_hint
        salary_text = _salary_text(item.get("salary"))
        employment_type = _employment_type(_optional_str(item.get("employmentType")))
        categories = _categories(item.get("categories"))
        requirements = ", ".join(part for part in (employment_type, categories) if part) or None
        combined = " ".join(
            part for part in (title, description or "", requirements or "", location or "") if part
        )
        return RawJob(
            source_name=self.name,
            source_job_id=source_job_id,
            company_name=_optional_str(item.get("companyName")) or "Unknown company",
            title=title,
            description=description or title,
            requirements=requirements,
            location=location,
            country=page.country,
            remote_type=_remote_type(combined),
            employment_type=employment_type,
            salary_original_text=salary_text,
            url=url,
            publication_date=_timestamp_millis(item.get("createDate"))
            or _timestamp_millis(item.get("updateDate")),
            raw_payload={
                "page_url": page.url,
                "key": source_job_id,
                "title": title,
                "company": item.get("companyName"),
                "categories": item.get("categories"),
                "salary": item.get("salary"),
                "location": location,
                "is_external": item.get("isExternalJob"),
            },
        )


def _matches_affinity(
    job: RawJob,
    queries: list[str],
    required_any_keywords: list[str],
    title_required_any_keywords: list[str],
    excluded_keywords: list[str],
    allowed_location_keywords: list[str],
) -> bool:
    haystack = f"{job.title} {job.description} {job.requirements or ''} {job.company_name}"
    title = job.title
    location = f"{job.location or ''} {job.country or ''}"
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


def _next_data(payload: str) -> dict[str, Any] | None:
    soup = BeautifulSoup(payload, "html.parser")
    script = soup.find("script", id="__NEXT_DATA__")
    if script is None:
        return None
    try:
        loaded = json.loads(script.get_text(strip=True))
    except json.JSONDecodeError:
        return None
    return loaded if isinstance(loaded, dict) else None


def _job_items(data: dict[str, Any]) -> list[dict[str, Any]]:
    sections = (
        data.get("props", {})
        .get("pageProps", {})
        .get("feed", {})
        .get("sections", [])
    )
    if not isinstance(sections, list):
        return []
    jobs: list[dict[str, Any]] = []
    for section in sections:
        if not isinstance(section, dict):
            continue
        items = section.get("items", [])
        if not isinstance(items, list):
            continue
        for item in items:
            if isinstance(item, dict) and item.get("type") == "job":
                payload = item.get("payload")
                if isinstance(payload, dict):
                    jobs.append(payload)
    return jobs


def _page_list(value: object) -> list[JobTodayPage]:
    if not isinstance(value, list):
        return []
    pages: list[JobTodayPage] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        url = _optional_str(item.get("url"))
        if url is None:
            continue
        pages.append(
            JobTodayPage(
                url=url,
                location_hint=_optional_str(item.get("location_hint")),
                country=_optional_str(item.get("country")) or "Spain",
            )
        )
    return pages


def _location(item: dict[str, Any], page: JobTodayPage) -> str | None:
    address_info = item.get("addressInfo")
    if isinstance(address_info, dict):
        display = address_info.get("display")
        if isinstance(display, dict):
            location = _optional_str(display.get("city")) or _optional_str(
                display.get("shortName")
            )
            if location is not None:
                return _with_location_hint(_normalized_location(location), page.location_hint)
    fallback = _normalized_location(_optional_str(item.get("address")))
    return _with_location_hint(fallback, page.location_hint)


def _salary_text(value: object) -> str | None:
    if not isinstance(value, dict) or not bool(value.get("isValid")):
        return None
    currency = _optional_str(value.get("currencyCode")) or "EUR"
    period = _salary_period(_optional_str(value.get("period")))
    lower = _optional_str(value.get("from"))
    upper = _optional_str(value.get("to"))
    if lower and upper:
        return f"Salary {lower}-{upper} {currency} {period}"
    if lower:
        return f"Salary {lower} {currency} {period}"
    if upper:
        return f"Salary {upper} {currency} {period}"
    return None


def _salary_period(value: str | None) -> str:
    normalized = (value or "").upper()
    if normalized == "MONTHLY":
        return "monthly"
    if normalized == "HOURLY":
        return "hourly"
    if normalized == "DAILY":
        return "daily"
    return "annual"


def _employment_type(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.upper()
    if normalized == "FULL_TIME":
        return "full_time"
    if normalized == "PART_TIME":
        return "part_time"
    return value.lower()


def _categories(value: object) -> str | None:
    if not isinstance(value, list):
        return None
    labels = [
        label
        for item in value
        if isinstance(item, dict)
        for label in [_optional_str(item.get("label"))]
        if label
    ]
    return ", ".join(labels) or None


def _remote_type(text: str) -> RemoteType:
    folded = _fold_text(text)
    if any(token in folded for token in ("teletrabajo", "remoto", "remote")):
        return RemoteType.REMOTE
    if any(token in folded for token in ("hibrido", "hybrid")):
        return RemoteType.HYBRID
    return RemoteType.ONSITE


def _timestamp_millis(value: object) -> datetime | None:
    if not isinstance(value, int | float):
        return None
    return datetime.fromtimestamp(value / 1000, UTC)


def _dedupe_jobs(jobs: list[RawJob]) -> list[RawJob]:
    seen: set[str] = set()
    deduped: list[RawJob] = []
    for job in jobs:
        key = job.source_job_id or f"{job.company_name}|{job.title}|{job.location}"
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


def _normalized_location(value: str | None) -> str | None:
    if value is None:
        return None
    folded = _fold_text(value)
    if folded == "seville":
        return "Sevilla"
    return value


def _with_location_hint(location: str | None, hint: str | None) -> str | None:
    if location is None or hint is None:
        return location
    folded_location = _fold_text(location)
    folded_hint = _fold_text(hint)
    if folded_hint in folded_location:
        return location
    return f"{location}, {hint}"


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _contains_keyword(text: str, keyword: str) -> bool:
    normalized = _fold_text(keyword).strip()
    if not normalized:
        return False
    escaped = re.escape(normalized).replace(r"\ ", r"\s+")
    return re.search(rf"(?<!\w){escaped}(?!\w)", _fold_text(text), re.IGNORECASE) is not None


def _fold_text(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.lower())
    return "".join(character for character in decomposed if not unicodedata.combining(character))
