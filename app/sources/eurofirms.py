from __future__ import annotations

import asyncio
import logging
import re
import unicodedata
from dataclasses import dataclass
from datetime import UTC, datetime
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
class EurofirmsPage:
    url: str
    location_hint: str | None
    country: str | None


class EurofirmsJobSource:
    name = "eurofirms"

    def __init__(self, settings: dict[str, Any]) -> None:
        self.enabled = bool(settings.get("enabled", True))
        self.base_url: str | None = str(settings.get("base_url", "https://jobs.eurofirms.com"))
        self.pages = _page_list(settings.get("pages", []))
        self.timeout_seconds = float(
            settings.get("timeout_seconds", get_settings().http_timeout_seconds)
        )
        self.retries = int(settings.get("retries", 2))
        self.rate_limit_seconds = float(settings.get("rate_limit_seconds", 2))
        self.min_interval_minutes = int(settings.get("min_interval_minutes", 360))
        self.minimum_score = int(settings.get("minimum_score", 50))
        self.max_jobs = int(settings.get("max_jobs", 20))
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
                        "No se pudo consultar la pagina de Eurofirms",
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

    async def _fetch_page(self, client: httpx.AsyncClient, page: EurofirmsPage) -> str:
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
                    "Fallo temporal consultando Eurofirms",
                    extra={"source": self.name, "url": page.url, "attempt": attempt + 1},
                )
                await asyncio.sleep(wait_seconds)
        raise RuntimeError(f"Eurofirms page failed after retries: {last_error}") from last_error

    def _jobs_from_html(self, payload: str, page: EurofirmsPage) -> list[RawJob]:
        soup = BeautifulSoup(payload, "html.parser")
        jobs: list[RawJob] = []
        for card in soup.select("article.psf-offer"):
            job = self._to_raw_job(card, page)
            if job is not None:
                jobs.append(job)
        return jobs

    def _to_raw_job(self, card: Tag, page: EurofirmsPage) -> RawJob | None:
        title = _text(card.select_one(".psf-offer__title"))
        location = _text(card.select_one(".psf-offer__site")) or page.location_hint
        description = _text(card.select_one(".psf-offer__description")) or title
        if title is None or description is None:
            return None
        url = _parent_url(card)
        info_text = _text(card.select_one(".psf-offer__info"))
        salary = _text(card.select_one(".info-block--salary"))
        combined = " ".join(
            part for part in (title, description, info_text or "", location or "") if part
        )
        return RawJob(
            source_name=self.name,
            source_job_id=_optional_str(card.get("data-ordercode"))
            or _optional_str(card.get("data-offerid"))
            or _source_job_id(url),
            company_name="Eurofirms",
            title=title,
            description=description,
            requirements=info_text,
            location=location,
            country=page.country,
            remote_type=_remote_type(combined),
            employment_type=_employment_type(combined),
            salary_original_text=salary,
            url=url,
            publication_date=_parse_date(info_text),
            raw_payload={
                "page_url": page.url,
                "title": title,
                "description": description,
                "location": location,
                "info": info_text,
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


def _page_list(value: object) -> list[EurofirmsPage]:
    if not isinstance(value, list):
        return []
    pages: list[EurofirmsPage] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        url = _optional_str(item.get("url"))
        if url is None:
            continue
        pages.append(
            EurofirmsPage(
                url=url,
                location_hint=_optional_str(item.get("location_hint")),
                country=_optional_str(item.get("country")) or "Spain",
            )
        )
    return pages


def _parent_url(card: Tag) -> str | None:
    parent = card.find_parent("a")
    if not isinstance(parent, Tag):
        return None
    href = _optional_str(parent.get("href"))
    if href is None:
        return None
    return urljoin("https://jobs.eurofirms.com", href)


def _source_job_id(url: str | None) -> str | None:
    if url is None:
        return None
    match = re.search(r"(?P<id>\d{3}-\d{6})(?:/?$|[?#])", url)
    if match:
        return match.group("id")
    return url.rstrip("/").rsplit("/", 1)[-1]


def _remote_type(text: str) -> RemoteType:
    folded = _fold_text(text)
    if any(token in folded for token in ("teletrabajo", "remoto", "remote")):
        return RemoteType.REMOTE
    if any(token in folded for token in ("hibrido", "hybrid")):
        return RemoteType.HYBRID
    return RemoteType.ONSITE


def _employment_type(text: str) -> str | None:
    folded = _fold_text(text)
    if "media jornada" in folded or "jornada parcial" in folded:
        return "part_time"
    if "jornada completa" in folded or "jornada intensiva" in folded:
        return "full_time"
    return None


def _parse_date(value: str | None) -> datetime | None:
    if value is None:
        return None
    match = re.search(r"\b(?P<date>\d{2}/\d{2}/\d{4})\b", value)
    if not match:
        return None
    try:
        parsed = datetime.strptime(match.group("date"), "%d/%m/%Y")
    except ValueError:
        return None
    return parsed.replace(tzinfo=UTC)


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
    folded_text = _fold_text(text)
    folded_keyword = _fold_text(keyword)
    if not folded_keyword:
        return False
    if re.fullmatch(r"[a-z0-9+#.]+(?: [a-z0-9+#.]+)*", folded_keyword):
        pattern = rf"(?<![a-z0-9+#.]){re.escape(folded_keyword)}(?![a-z0-9+#.])"
        return re.search(pattern, folded_text) is not None
    return folded_keyword in folded_text


def _fold_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.casefold())
    return "".join(char for char in normalized if not unicodedata.combining(char))
