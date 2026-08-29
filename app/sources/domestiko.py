from __future__ import annotations

import asyncio
import json
import logging
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from app.core.config import get_settings
from app.models.enums import RemoteType
from app.sources.base import RawJob, SearchConfig

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DomestikoPage:
    url: str


class DomestikoJobSource:
    name = "domestiko"

    def __init__(self, settings: dict[str, Any]) -> None:
        self.enabled = bool(settings.get("enabled", True))
        self.base_url: str | None = str(settings.get("base_url", "https://www.domestiko.com"))
        self.pages = _page_list(settings.get("pages", []))
        self.timeout_seconds = float(
            settings.get("timeout_seconds", get_settings().http_timeout_seconds)
        )
        self.retries = int(settings.get("retries", 2))
        self.rate_limit_seconds = float(settings.get("rate_limit_seconds", 1))
        self.min_interval_minutes = int(settings.get("min_interval_minutes", 360))
        self.minimum_score = int(settings.get("minimum_score", 45))
        self.max_jobs = int(settings.get("max_jobs", 40))
        self.max_links_per_page = int(settings.get("max_links_per_page", 12))
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
                links = await self._offer_links(client, page)
                for link in links[: self.max_links_per_page]:
                    job = await self._fetch_offer(client, link)
                    if job is not None:
                        jobs.append(job)
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

    async def _offer_links(self, client: httpx.AsyncClient, page: DomestikoPage) -> list[str]:
        try:
            payload = await self._fetch_payload(client, page.url)
        except RuntimeError:
            logger.warning(
                "No se pudo consultar la pagina de Domestiko",
                extra={"source": self.name, "url": page.url},
            )
            return []
        soup = BeautifulSoup(payload, "html.parser")
        links: list[str] = []
        for anchor in soup.find_all("a", href=True):
            href = str(anchor.get("href") or "")
            if "/empleo/oferta/" not in href:
                continue
            url = urljoin(str(self.base_url), href)
            if url not in links:
                links.append(url)
        return links

    async def _fetch_offer(self, client: httpx.AsyncClient, url: str) -> RawJob | None:
        try:
            payload = await self._fetch_payload(client, url)
        except RuntimeError:
            logger.warning(
                "No se pudo consultar la oferta de Domestiko",
                extra={"source": self.name, "url": url},
            )
            return None
        posting = _job_posting(payload)
        if posting is None:
            return None
        return _raw_job_from_posting(self.name, url, posting)

    async def _fetch_payload(self, client: httpx.AsyncClient, url: str) -> str:
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
                    "Fallo temporal consultando Domestiko",
                    extra={"source": self.name, "url": url, "attempt": attempt + 1},
                )
                await asyncio.sleep(wait_seconds)
        raise RuntimeError(f"Domestiko request failed after retries: {last_error}") from last_error


def _matches_affinity(
    job: RawJob,
    queries: list[str],
    required_any_keywords: list[str],
    title_required_any_keywords: list[str],
    excluded_keywords: list[str],
    allowed_location_keywords: list[str],
) -> bool:
    haystack = f"{job.title} {job.description} {job.requirements or ''}"
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
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            loaded = json.loads(script.get_text(strip=True))
        except json.JSONDecodeError:
            continue
        items = loaded if isinstance(loaded, list) else [loaded]
        for item in items:
            if isinstance(item, dict) and item.get("@type") == "JobPosting":
                return item
    return None


def _raw_job_from_posting(source_name: str, url: str, posting: dict[str, Any]) -> RawJob:
    description = str(posting.get("description") or "")
    title = _clean_title(str(posting.get("title") or "Untitled job"))
    employment_type = _employment_type(posting.get("employmentType"))
    location, country = _location(posting.get("jobLocation"))
    return RawJob(
        source_name=source_name,
        source_job_id=_source_job_id(posting, url),
        company_name=_company_name(posting.get("hiringOrganization")),
        title=title,
        description=description,
        requirements=employment_type,
        location=location,
        country=country,
        remote_type=_remote_type(description),
        employment_type=employment_type,
        url=url,
        publication_date=_parse_datetime(posting.get("datePosted")),
        expiration_date=_parse_datetime(posting.get("validThrough")),
        raw_payload=dict(posting),
    )


def _page_list(value: object) -> list[DomestikoPage]:
    if not isinstance(value, list):
        return []
    pages: list[DomestikoPage] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        url = _optional_str(item.get("url"))
        if url is not None:
            pages.append(DomestikoPage(url))
    return pages


def _clean_title(value: str) -> str:
    title = re.sub(r"\s*\(Administraci[oó]n y secretariado\)\s*$", "", value)
    return re.sub(r"\s+", " ", title).strip() or "Untitled job"


def _source_job_id(posting: dict[str, Any], url: str) -> str:
    identifier = posting.get("identifier")
    if isinstance(identifier, dict):
        value = _optional_str(identifier.get("value"))
        if value is not None:
            return value
    return url.rstrip("/").rsplit("/", 1)[-1]


def _company_name(value: object) -> str:
    if isinstance(value, dict):
        name = _optional_str(value.get("name"))
        if name is not None:
            return name
    return "Domestiko.com"


def _location(value: object) -> tuple[str | None, str | None]:
    if not isinstance(value, dict):
        return None, None
    address = value.get("address")
    if not isinstance(address, dict):
        return None, None
    locality = _title_location(_optional_str(address.get("addressLocality")))
    region = _title_location(_optional_str(address.get("addressRegion")))
    country_code = _optional_str(address.get("addressCountry"))
    parts = [part for part in (locality, region) if part]
    country = "Spain" if country_code == "ES" else country_code
    return ", ".join(parts) or None, country


def _title_location(value: str | None) -> str | None:
    if value is None:
        return None
    text = value.title()
    return text.replace("Almeria", "Almeria")


def _employment_type(value: object) -> str | None:
    text = _optional_str(value)
    if text is None:
        return None
    normalized = text.upper()
    if normalized == "FULL_TIME":
        return "full_time"
    if normalized == "PART_TIME":
        return "part_time"
    return text.lower()


def _remote_type(text: str) -> RemoteType:
    folded = _fold_text(text)
    if any(token in folded for token in ("teletrabajo", "remoto", "remote")):
        return RemoteType.REMOTE
    if any(token in folded for token in ("hibrido", "hybrid")):
        return RemoteType.HYBRID
    return RemoteType.ONSITE


def _parse_datetime(value: object) -> datetime | None:
    text = _optional_str(value)
    if text is None:
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
    normalized = _fold_text(keyword).strip()
    if not normalized:
        return False
    escaped = re.escape(normalized).replace(r"\ ", r"\s+")
    return re.search(rf"(?<!\w){escaped}(?!\w)", _fold_text(text), re.IGNORECASE) is not None


def _fold_text(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.lower())
    return "".join(character for character in decomposed if not unicodedata.combining(character))
