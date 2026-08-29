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
from bs4.element import Tag

from app.core.config import get_settings
from app.models.enums import RemoteType
from app.sources.base import RawJob, SearchConfig

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PagePersonnelPage:
    url: str
    location_hint: str | None
    country: str | None


class PagePersonnelJobSource:
    name = "pagepersonnel"

    def __init__(self, settings: dict[str, Any]) -> None:
        self.enabled = bool(settings.get("enabled", True))
        self.base_url: str | None = str(settings.get("base_url", "https://www.pagepersonnel.es"))
        self.pages = _page_list(settings.get("pages", []))
        self.timeout_seconds = float(
            settings.get("timeout_seconds", get_settings().http_timeout_seconds)
        )
        self.retries = int(settings.get("retries", 2))
        self.rate_limit_seconds = float(settings.get("rate_limit_seconds", 2))
        self.min_interval_minutes = int(settings.get("min_interval_minutes", 360))
        self.minimum_score = int(settings.get("minimum_score", 50))
        self.max_jobs = int(settings.get("max_jobs", 20))
        self.include_recommended = bool(settings.get("include_recommended", False))
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
                        "No se pudo consultar la pagina de Page Personnel",
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

    async def _fetch_page(self, client: httpx.AsyncClient, page: PagePersonnelPage) -> str:
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
                    "Fallo temporal consultando Page Personnel",
                    extra={"source": self.name, "url": page.url, "attempt": attempt + 1},
                )
                await asyncio.sleep(wait_seconds)
        raise RuntimeError(
            f"Page Personnel page failed after retries: {last_error}"
        ) from last_error

    def _jobs_from_html(self, payload: str, page: PagePersonnelPage) -> list[RawJob]:
        soup = BeautifulSoup(payload, "html.parser")
        jobs: list[RawJob] = []
        for card in soup.select("div.job-tile.search-job-tile"):
            classes = set(_string_list(card.get("class")))
            if not self.include_recommended and "recommended-job-tile" in classes:
                continue
            job = self._to_raw_job(card, page)
            if job is not None:
                jobs.append(job)
        return jobs

    def _to_raw_job(self, card: Tag, page: PagePersonnelPage) -> RawJob | None:
        link = card.select_one(".job-title a")
        if not isinstance(link, Tag):
            return None
        title = _clean_text(link.get_text(" ", strip=True))
        href = _optional_str(link.get("href"))
        if title is None or href is None:
            return None
        url = urljoin(str(self.base_url), href)
        location = _text(card.select_one(".job-location")) or page.location_hint
        summary = _text(card.select_one(".job-summary"))
        bullets = _text(card.select_one(".job_advert__job-desc-bullet-points"))
        description = " ".join(part for part in (summary, bullets) if part) or title
        salary = _salary_text(_text(card.select_one(".job-salary")))
        job_nature = _text(card.select_one(".job-nature"))
        combined = " ".join(
            part
            for part in (title, description, salary or "", job_nature or "", location or "")
            if part
        )
        return RawJob(
            source_name=self.name,
            source_job_id=_source_job_id(href),
            company_name="Page Personnel",
            title=title.rstrip("."),
            description=description,
            requirements=None,
            location=location,
            country=page.country,
            remote_type=_remote_type(combined),
            salary_original_text=salary,
            url=url,
            raw_payload={
                "page_url": page.url,
                "title": title,
                "description": description,
                "location": location,
                "salary": salary,
                "job_nature": job_nature,
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


def _page_list(value: object) -> list[PagePersonnelPage]:
    if not isinstance(value, list):
        return []
    pages: list[PagePersonnelPage] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        url = _optional_str(item.get("url"))
        if url is None:
            continue
        pages.append(
            PagePersonnelPage(
                url=url,
                location_hint=_optional_str(item.get("location_hint")),
                country=_optional_str(item.get("country")) or "Spain",
            )
        )
    return pages


def _source_job_id(href: str) -> str:
    match = re.search(r"/ref/(?P<id>[^/?#]+)", href)
    if match:
        return match.group("id")
    return href.rstrip("/").rsplit("/", 1)[-1]


def _remote_type(text: str) -> RemoteType:
    folded = _fold_text(text)
    if any(token in folded for token in ("hibrido", "hybrid")):
        return RemoteType.HYBRID
    if any(token in folded for token in ("teletrabajo", "remoto", "remote")):
        return RemoteType.REMOTE
    return RemoteType.ONSITE


def _salary_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = _clean_text(value)
    if cleaned is None:
        return None
    match = re.search(
        r"(?:EUR|€)\s*(?P<min>\d[\d.]*)\s*-\s*(?:EUR|€)?\s*(?P<max>\d[\d.]*)"
        r"(?:\s*(?P<period>por año|al año|por mes|al mes))?",
        cleaned,
        re.IGNORECASE,
    )
    if match:
        min_value = _pagepersonnel_amount(match.group("min"), cleaned)
        max_value = _pagepersonnel_amount(match.group("max"), cleaned)
        period = _salary_period(match.group("period"))
        return f"{min_value}-{max_value} EUR {period}"
    single = re.search(
        r"(?:EUR|€)\s*(?P<amount>\d[\d.]*)"
        r"(?:\s*(?P<period>por año|al año|por mes|al mes))?",
        cleaned,
        re.IGNORECASE,
    )
    if single:
        amount = _pagepersonnel_amount(single.group("amount"), cleaned)
        period = _salary_period(single.group("period"))
        return f"{amount} EUR {period}"
    return cleaned


def _pagepersonnel_amount(raw: str, context: str) -> int:
    amount = int(raw.replace(".", ""))
    folded_context = _fold_text(context)
    if amount < 1000 and ("ano" in folded_context or "year" in folded_context):
        return amount * 1000
    return amount


def _salary_period(value: str | None) -> str:
    folded = _fold_text(value or "")
    if "mes" in folded:
        return "al mes"
    return "al año"


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
    if not isinstance(value, list | tuple):
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
