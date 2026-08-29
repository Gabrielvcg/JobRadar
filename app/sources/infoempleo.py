from __future__ import annotations

import asyncio
import logging
import re
import unicodedata
from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup
from bs4.element import NavigableString, Tag

from app.core.config import get_settings
from app.models.enums import RemoteType
from app.sources.base import RawJob, SearchConfig

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class InfoempleoPage:
    url: str
    location_hint: str | None
    country: str | None


class InfoempleoJobSource:
    name = "infoempleo"

    def __init__(self, settings: dict[str, Any]) -> None:
        self.enabled = bool(settings.get("enabled", True))
        self.base_url: str | None = str(settings.get("base_url", "https://www.infoempleo.com"))
        self.pages = _page_list(settings.get("pages", []))
        self.timeout_seconds = float(
            settings.get("timeout_seconds", get_settings().http_timeout_seconds)
        )
        self.retries = int(settings.get("retries", 2))
        self.rate_limit_seconds = float(settings.get("rate_limit_seconds", 2))
        self.min_interval_minutes = int(settings.get("min_interval_minutes", 360))
        self.minimum_score = int(settings.get("minimum_score", 35))
        self.max_jobs = int(settings.get("max_jobs", 100))
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
                        "No se pudo consultar la pagina de Infoempleo",
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

    async def _fetch_page(self, client: httpx.AsyncClient, page: InfoempleoPage) -> str:
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
                    "Fallo temporal consultando Infoempleo",
                    extra={
                        "source": self.name,
                        "url": page.url,
                        "attempt": attempt + 1,
                    },
                )
                await asyncio.sleep(wait_seconds)
        raise RuntimeError(f"Infoempleo page failed after retries: {last_error}") from last_error

    def _jobs_from_html(self, payload: str, page: InfoempleoPage) -> list[RawJob]:
        soup = BeautifulSoup(payload, "html.parser")
        jobs: list[RawJob] = []
        for block in soup.select("li.offerblock"):
            job = self._to_raw_job(block, page)
            if job is not None:
                jobs.append(job)
        return jobs

    def _to_raw_job(self, block: Tag, page: InfoempleoPage) -> RawJob | None:
        link = block.select_one("h2.title a")
        if not isinstance(link, Tag):
            return None
        title = _clean_text(link.get_text(" ", strip=True))
        href = _optional_str(link.get("href"))
        if not title or not href:
            return None
        url = urljoin(str(self.base_url), href)
        description = _direct_text(block.select_one("p.trunkat")) or ""
        meta = _direct_text(block.select_one("p.small.extra-data"))
        company = _company_name(block) or "Unknown company"
        combined = " ".join(part for part in (title, description, meta or "") if part)
        return RawJob(
            source_name=self.name,
            source_job_id=_source_job_id(href),
            company_name=company,
            title=title,
            description=description,
            requirements=meta,
            location=page.location_hint,
            country=page.country,
            remote_type=_remote_type(combined),
            employment_type=_employment_type(meta),
            salary_original_text=_salary_text(meta),
            url=url,
            raw_payload={
                "page_url": page.url,
                "title": title,
                "company": company,
                "description": description,
                "meta": meta,
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


def _page_list(value: object) -> list[InfoempleoPage]:
    if not isinstance(value, list):
        return []
    pages: list[InfoempleoPage] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        url = _optional_str(item.get("url"))
        if url is None:
            continue
        pages.append(
            InfoempleoPage(
                url=url,
                location_hint=_optional_str(item.get("location_hint")),
                country=_optional_str(item.get("country")) or "Spain",
            )
        )
    return pages


def _company_name(block: Tag) -> str | None:
    company = block.select_one("div.logoplusname span.extra-data")
    if isinstance(company, Tag):
        return _clean_text(company.get_text(" ", strip=True))
    logo = block.select_one("div.logoplusname img")
    if isinstance(logo, Tag):
        return _optional_str(logo.get("alt"))
    return None


def _direct_text(element: Tag | None) -> str | None:
    if element is None:
        return None
    parts = [
        str(child).strip()
        for child in element.children
        if isinstance(child, NavigableString) and str(child).strip()
    ]
    return _clean_text(" ".join(parts))


def _remote_type(text: str) -> RemoteType:
    folded = _fold_text(text)
    if any(token in folded for token in ("teletrabajo", "remoto", "remote")):
        return RemoteType.REMOTE
    if any(token in folded for token in ("hibrido", "hybrid")):
        return RemoteType.HYBRID
    if "presencial" in folded:
        return RemoteType.ONSITE
    return RemoteType.ONSITE


def _employment_type(meta: str | None) -> str | None:
    if meta is None:
        return None
    folded = _fold_text(meta)
    if "jornada completa" in folded:
        return "full_time"
    if "media jornada" in folded or "jornada parcial" in folded:
        return "part_time"
    return None


def _salary_text(meta: str | None) -> str | None:
    if not meta or "salario" not in _fold_text(meta):
        return None
    return meta


def _source_job_id(href: str) -> str:
    match = re.search(r"/(?P<id>\d+)/?$", href)
    if match:
        return match.group("id")
    return href.strip()


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
