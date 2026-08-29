from __future__ import annotations

import asyncio
import json
import logging
import re
import unicodedata
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import parse_qs, urljoin, urlparse

import httpx
from bs4 import BeautifulSoup
from bs4.element import Tag

from app.core.config import get_settings
from app.models.enums import RemoteType
from app.sources.base import RawJob, SearchConfig

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TalentPage:
    url: str
    location_hint: str | None
    country: str | None


class TalentJobSource:
    name = "talent"

    def __init__(self, settings: dict[str, Any]) -> None:
        self.enabled = bool(settings.get("enabled", True))
        self.base_url: str | None = str(settings.get("base_url", "https://es.talent.com"))
        self.pages = _page_list(settings.get("pages", []))
        self.timeout_seconds = float(
            settings.get("timeout_seconds", get_settings().http_timeout_seconds)
        )
        self.retries = int(settings.get("retries", 2))
        self.rate_limit_seconds = float(settings.get("rate_limit_seconds", 1))
        self.detail_rate_limit_seconds = float(settings.get("detail_rate_limit_seconds", 0.5))
        self.min_interval_minutes = int(settings.get("min_interval_minutes", 360))
        self.minimum_score = int(settings.get("minimum_score", 45))
        self.max_jobs = int(settings.get("max_jobs", 60))
        self.max_detail_pages = int(settings.get("max_detail_pages", 24))
        self.fetch_detail_pages = bool(settings.get("fetch_detail_pages", True))
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
                    payload = await self._fetch_page(client, page.url)
                except RuntimeError:
                    logger.warning(
                        "No se pudo consultar la pagina de Talent.com",
                        extra={"source": self.name, "url": page.url},
                    )
                    continue
                jobs.extend(self._jobs_from_html(payload, page))
                await asyncio.sleep(self.rate_limit_seconds)

            jobs = _dedupe_jobs(jobs)
            if self.strict_search_filter:
                jobs = self._filter_jobs(jobs, search_config)
            if self.fetch_detail_pages:
                jobs = await self._enrich_jobs(client, jobs[: self.max_detail_pages])

        jobs = _dedupe_jobs(jobs)
        if self.strict_search_filter:
            jobs = self._filter_jobs(jobs, search_config)
        return jobs[: self.max_jobs]

    async def _fetch_page(self, client: httpx.AsyncClient, url: str) -> str:
        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                response = await client.get(url)
                response.raise_for_status()
                return response.text
            except httpx.HTTPError as exc:
                last_error = exc
                wait_seconds = min(2**attempt, 8)
                logger.warning(
                    "Fallo temporal consultando Talent.com",
                    extra={"source": self.name, "url": url, "attempt": attempt + 1},
                )
                await asyncio.sleep(wait_seconds)
        raise RuntimeError(f"Talent.com page failed after retries: {last_error}") from last_error

    def _jobs_from_html(self, payload: str, page: TalentPage) -> list[RawJob]:
        soup = BeautifulSoup(payload, "html.parser")
        jobs: list[RawJob] = []
        for card in soup.select('article[data-testid="job-card-unified"]'):
            job = self._to_raw_job(card, page)
            if job is not None:
                jobs.append(job)
        return jobs

    def _to_raw_job(self, card: Tag, page: TalentPage) -> RawJob | None:
        link = card.select_one('a[href*="/view?id="]')
        title = _text(card.select_one('[class*="JobCard_title"]'))
        href = _optional_str(link.get("href")) if isinstance(link, Tag) else None
        if title is None or href is None:
            return None
        url = urljoin(str(self.base_url), href)
        company = _text(card.select_one('[class*="JobCard_company"]')) or "Unknown company"
        location = _text(card.select_one('[class*="JobCard_location"]')) or page.location_hint
        snippet = _text(card.select_one('[class*="JobCard_snippet"]')) or title
        time_label = _text(card.select_one('[class*="JobCard_timeText"]'))
        combined = card.get_text(" ", strip=True)
        return RawJob(
            source_name=self.name,
            source_job_id=_source_job_id(url),
            company_name=company,
            title=title.rstrip("."),
            description=snippet,
            requirements=time_label,
            location=_with_location_hint(location, page.location_hint),
            country=page.country,
            remote_type=_remote_type(combined),
            salary_original_text=_salary_text(combined),
            url=url,
            publication_date=_relative_publication_date(time_label),
            raw_payload={
                "page_url": page.url,
                "title": title,
                "company": company,
                "location": location,
                "snippet": snippet,
                "time_label": time_label,
            },
        )

    async def _enrich_jobs(self, client: httpx.AsyncClient, jobs: list[RawJob]) -> list[RawJob]:
        enriched: list[RawJob] = []
        for job in jobs:
            if job.url is None:
                enriched.append(job)
                continue
            try:
                payload = await self._fetch_page(client, job.url)
            except RuntimeError:
                enriched.append(job)
                continue
            enriched.append(_enriched_from_detail(job, payload))
            await asyncio.sleep(self.detail_rate_limit_seconds)
        return enriched

    def _filter_jobs(self, jobs: list[RawJob], search_config: SearchConfig) -> list[RawJob]:
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


def _enriched_from_detail(job: RawJob, payload: str) -> RawJob:
    posting = _job_posting(payload)
    if posting is None:
        return job
    title = _optional_str(posting.get("title")) or job.title
    description = _html_to_text(_optional_str(posting.get("description"))) or job.description
    company = _posting_company(posting) or job.company_name
    location = _posting_location(posting) or job.location
    salary = _base_salary_text(posting.get("baseSalary")) or job.salary_original_text
    publication_date = _parse_date(_optional_str(posting.get("datePosted"))) or job.publication_date
    expiration_date = _parse_date(_optional_str(posting.get("validThrough"))) or job.expiration_date
    return replace(
        job,
        title=title.rstrip("."),
        description=description,
        company_name=company,
        location=location,
        salary_original_text=salary,
        publication_date=publication_date,
        expiration_date=expiration_date,
        raw_payload={**job.raw_payload, "detail_json_ld": posting},
    )


def _matches_affinity(
    job: RawJob,
    queries: list[str],
    required_any_keywords: list[str],
    title_required_any_keywords: list[str],
    excluded_keywords: list[str],
    allowed_location_keywords: list[str],
) -> bool:
    haystack = " ".join(
        part
        for part in (
            job.title,
            job.description,
            job.requirements or "",
            job.company_name,
            job.location or "",
        )
        if part
    )
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


def _job_posting(payload: str) -> dict[str, Any] | None:
    soup = BeautifulSoup(payload, "html.parser")
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            data = json.loads(script.get_text(strip=True))
        except json.JSONDecodeError:
            continue
        found = _find_job_posting(data)
        if found is not None:
            return found
    return None


def _find_job_posting(value: object) -> dict[str, Any] | None:
    if isinstance(value, dict):
        raw_type = value.get("@type")
        types = raw_type if isinstance(raw_type, list) else [raw_type]
        if any(str(item).lower() == "jobposting" for item in types if item is not None):
            return value
        graph = value.get("@graph")
        found = _find_job_posting(graph)
        if found is not None:
            return found
        for child in value.values():
            found = _find_job_posting(child)
            if found is not None:
                return found
    if isinstance(value, list):
        for item in value:
            found = _find_job_posting(item)
            if found is not None:
                return found
    return None


def _posting_company(posting: dict[str, Any]) -> str | None:
    organization = posting.get("hiringOrganization")
    if isinstance(organization, dict):
        return _optional_str(organization.get("name"))
    return _optional_str(organization)


def _posting_location(posting: dict[str, Any]) -> str | None:
    location = posting.get("jobLocation")
    if isinstance(location, list):
        locations = [_posting_location({"jobLocation": item}) for item in location]
        return ", ".join(item for item in locations if item) or None
    if not isinstance(location, dict):
        return _optional_str(location)
    address = location.get("address")
    if isinstance(address, dict):
        parts = [
            _optional_str(address.get("addressLocality")),
            _optional_str(address.get("addressRegion")),
            _optional_str(address.get("addressCountry")),
        ]
        return ", ".join(part for part in parts if part) or None
    return _optional_str(location.get("name"))


def _base_salary_text(value: object) -> str | None:
    if not isinstance(value, dict):
        return None
    currency = _optional_str(value.get("currency")) or "EUR"
    raw_value = value.get("value")
    if isinstance(raw_value, dict):
        unit = _optional_str(raw_value.get("unitText")) or "annual"
        minimum = _optional_str(raw_value.get("minValue"))
        maximum = _optional_str(raw_value.get("maxValue"))
        exact = _optional_str(raw_value.get("value"))
        if minimum and maximum:
            return f"Salary {minimum}-{maximum} {currency} {unit.lower()}"
        if exact:
            return f"Salary {exact} {currency} {unit.lower()}"
        if minimum:
            return f"Salary {minimum} {currency} {unit.lower()}"
    return None


def _page_list(value: object) -> list[TalentPage]:
    if not isinstance(value, list):
        return []
    pages: list[TalentPage] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        url = _optional_str(item.get("url"))
        if url is None:
            continue
        pages.append(
            TalentPage(
                url=url,
                location_hint=_optional_str(item.get("location_hint")),
                country=_optional_str(item.get("country")) or "Spain",
            )
        )
    return pages


def _source_job_id(url: str) -> str:
    parsed = urlparse(url)
    values = parse_qs(parsed.query).get("id")
    if values and values[0]:
        return values[0]
    return url.rstrip("/").rsplit("/", 1)[-1]


def _remote_type(text: str) -> RemoteType:
    folded = _fold_text(text)
    if any(token in folded for token in ("teletrabajo", "remoto", "remote")):
        return RemoteType.REMOTE
    if any(token in folded for token in ("hibrido", "hybrid")):
        return RemoteType.HYBRID
    return RemoteType.ONSITE


def _salary_text(text: str) -> str | None:
    match = re.search(
        r"((?:\d{1,3}(?:[.\s]\d{3})+|\d+)(?:,\d+)?\s*(?:€|eur|usd)"
        r"(?:\s*(?:-|a|to)\s*(?:\d{1,3}(?:[.\s]\d{3})+|\d+)(?:,\d+)?\s*(?:€|eur|usd)?)?"
        r"(?:\s*(?:/|al|por)?\s*(?:año|ano|mes|hora|year|month|hour|annual|monthly|hourly))?)",
        text,
        re.IGNORECASE,
    )
    return _clean_text(match.group(1)) if match else None


def _relative_publication_date(value: str | None) -> datetime | None:
    if value is None:
        return None
    folded = _fold_text(value)
    now = datetime.now(UTC)
    match = re.search(r"hace\s+mas\s+de\s+(\d+)\s+d", folded)
    if match:
        return now - timedelta(days=int(match.group(1)) + 1)
    match = re.search(r"hace\s+(\d+)\s+(hora|dia|semana|mes)", folded)
    if not match:
        return now if "hoy" in folded else None
    amount = int(match.group(1))
    unit = match.group(2)
    if unit.startswith("hora"):
        return now - timedelta(hours=amount)
    if unit.startswith("dia"):
        return now - timedelta(days=amount)
    if unit.startswith("semana"):
        return now - timedelta(days=amount * 7)
    if unit.startswith("mes"):
        return now - timedelta(days=amount * 30)
    return None


def _parse_date(value: str | None) -> datetime | None:
    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        return None
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    for parser in (
        lambda raw: datetime.fromisoformat(raw),
        lambda raw: datetime.strptime(raw, "%Y%m%dT%H%M%S").replace(tzinfo=UTC),
        lambda raw: datetime.strptime(raw, "%Y-%m-%d").replace(tzinfo=UTC),
    ):
        try:
            parsed = parser(normalized)
        except ValueError:
            continue
        return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)
    return None


def _with_location_hint(location: str | None, hint: str | None) -> str | None:
    if location is None or hint is None:
        return location
    if _contains_keyword(location, hint):
        return location
    return f"{location}, {hint}"


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


def _html_to_text(value: str | None) -> str | None:
    if value is None:
        return None
    return _clean_text(BeautifulSoup(value, "html.parser").get_text(" ", strip=True))


def _text(element: Tag | None) -> str | None:
    if element is None:
        return None
    return _clean_text(element.get_text(" ", strip=True))


def _clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    text = re.sub(r"\s+", " ", value).strip()
    return text or None


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
    normalized = _fold_text(keyword).strip()
    if not normalized:
        return False
    escaped = re.escape(normalized).replace(r"\ ", r"\s+")
    return re.search(rf"(?<!\w){escaped}(?!\w)", _fold_text(text), re.IGNORECASE) is not None


def _fold_text(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.lower())
    return "".join(character for character in decomposed if not unicodedata.combining(character))
