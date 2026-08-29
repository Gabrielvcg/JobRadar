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
from bs4.element import Tag

from app.core.config import get_settings
from app.models.enums import RemoteType
from app.sources.base import RawJob, SearchConfig

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class FundacionAdeccoPage:
    url: str
    location_hint: str | None
    country: str | None


class FundacionAdeccoJobSource:
    name = "fundacion_adecco"

    def __init__(self, settings: dict[str, Any]) -> None:
        self.enabled = bool(settings.get("enabled", True))
        self.base_url: str | None = str(
            settings.get("base_url", "https://empleo.fundacionadecco.org")
        )
        self.pages = _page_list(settings.get("pages", []))
        self.timeout_seconds = float(
            settings.get("timeout_seconds", get_settings().http_timeout_seconds)
        )
        self.retries = int(settings.get("retries", 2))
        self.rate_limit_seconds = float(settings.get("rate_limit_seconds", 2))
        self.detail_rate_limit_seconds = float(settings.get("detail_rate_limit_seconds", 1.5))
        self.min_interval_minutes = int(settings.get("min_interval_minutes", 360))
        self.minimum_score = int(settings.get("minimum_score", 35))
        self.max_jobs = int(settings.get("max_jobs", 50))
        self.enrich_details = bool(settings.get("enrich_details", True))
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
                        "No se pudo consultar la pagina de Fundación Adecco",
                        extra={"source": self.name, "url": page.url},
                    )
                    continue
                listing_jobs = self._jobs_from_listing(payload, page)
                if self.enrich_details:
                    listing_jobs = await self._enrich_jobs(client, listing_jobs)
                jobs.extend(listing_jobs)
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
                    "Fallo temporal consultando Fundación Adecco",
                    extra={"source": self.name, "url": url, "attempt": attempt + 1},
                )
                await asyncio.sleep(wait_seconds)
        msg = f"Fundacion Adecco page failed after retries: {last_error}"
        raise RuntimeError(msg) from last_error

    def _jobs_from_listing(self, payload: str, page: FundacionAdeccoPage) -> list[RawJob]:
        soup = BeautifulSoup(payload, "html.parser")
        jobs = [
            job for job in (self._to_raw_job(card, page) for card in _listing_cards(soup)) if job
        ]
        if jobs:
            return jobs
        return [
            RawJob(
                source_name=self.name,
                source_job_id=_source_job_id(url),
                company_name="Fundación Adecco",
                title=_title_from_url(url),
                description="",
                location=page.location_hint,
                country=page.country,
                url=url,
            )
            for url in _item_list_urls(soup)
        ]

    def _to_raw_job(self, card: Tag, page: FundacionAdeccoPage) -> RawJob | None:
        link = card.select_one(".search-result-job-title a[href]")
        if not isinstance(link, Tag):
            return None
        href = _optional_str(link.get("href"))
        title = _clean_text(link.get_text(" ", strip=True))
        if href is None or title is None:
            return None
        url = urljoin(str(self.base_url), href)
        details = _text(card.select_one(".search-result-job-details"))
        bottom_details = [
            _clean_text(element.get_text(" ", strip=True))
            for element in card.select(".search-result-bottom-details-text")
            if isinstance(element, Tag)
        ]
        disability = _text(card.select_one(".search-result-disability-certificate-label"))
        requirements = ", ".join(
            part for part in [details, *bottom_details, disability] if part
        ) or None
        return RawJob(
            source_name=self.name,
            source_job_id=_optional_str(link.get("data-id")) or _source_job_id(url),
            company_name="Fundación Adecco",
            title=_strip_location_suffix(title),
            description=requirements or "",
            requirements=requirements,
            location=_location_from_details(details) or page.location_hint,
            country=page.country,
            remote_type=_remote_type(f"{title} {requirements or ''}"),
            employment_type=_employment_type(requirements),
            salary_original_text=_salary_text(requirements),
            url=url,
            publication_date=_publication_date(details),
            raw_payload={"page_url": page.url, "title": title, "details": requirements},
        )

    async def _enrich_jobs(self, client: httpx.AsyncClient, jobs: list[RawJob]) -> list[RawJob]:
        enriched: list[RawJob] = []
        for job in jobs:
            if not job.url:
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


def _enriched_from_detail(job: RawJob, payload: str) -> RawJob:
    soup = BeautifulSoup(payload, "html.parser")
    title = _text(soup.select_one("h1")) or job.title
    paragraphs = [
        _clean_text(block.get_text(" ", strip=True))
        for block in soup.select(".job-info-paragraph")
    ]
    sections = [paragraph for paragraph in paragraphs if paragraph]
    description = sections[0] if sections else job.description
    requirements = " ".join(sections[1:]) or job.requirements
    combined = f"{title} {description} {requirements or ''}"
    location = _detail_location(soup) or job.location
    return RawJob(
        source_name=job.source_name,
        source_job_id=job.source_job_id or _source_job_id(job.url),
        company_name=job.company_name,
        title=_strip_location_suffix(title),
        description=description,
        requirements=requirements,
        location=location,
        country=job.country,
        remote_type=_remote_type(combined),
        employment_type=job.employment_type or _employment_type(combined),
        salary_original_text=_salary_text(combined) or job.salary_original_text,
        url=job.url,
        publication_date=job.publication_date or _publication_date(combined),
        expiration_date=job.expiration_date,
        company_website=job.company_website,
        raw_payload={**job.raw_payload, "detail_enriched": True},
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


def _listing_cards(soup: BeautifulSoup) -> list[Tag]:
    return [card for card in soup.select(".search-result-card") if isinstance(card, Tag)]


def _item_list_urls(soup: BeautifulSoup) -> list[str]:
    urls: list[str] = []
    for script in soup.select('script[type="application/ld+json"]'):
        if not isinstance(script, Tag):
            continue
        try:
            payload = json.loads(script.get_text(strip=True))
        except json.JSONDecodeError:
            continue
        elements = payload.get("itemListElement") if isinstance(payload, dict) else None
        if not isinstance(elements, list):
            continue
        for item in elements:
            if isinstance(item, dict):
                url = _optional_str(item.get("url"))
                if url:
                    urls.append(url)
    return urls


def _page_list(value: object) -> list[FundacionAdeccoPage]:
    if not isinstance(value, list):
        return []
    pages: list[FundacionAdeccoPage] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        url = _optional_str(item.get("url"))
        if url is None:
            continue
        pages.append(
            FundacionAdeccoPage(
                url=url,
                location_hint=_optional_str(item.get("location_hint")),
                country=_optional_str(item.get("country")) or "Spain",
            )
        )
    return pages


def _source_job_id(url: str | None) -> str | None:
    if url is None:
        return None
    match = re.search(r"/oferta-empleo/[^_]+_(?P<id>[^/?#]+)", url)
    if match:
        return match.group("id")
    return url.rstrip("/").rsplit("/", 1)[-1]


def _title_from_url(url: str) -> str:
    slug = url.rstrip("/").rsplit("/", 1)[-1].split("_", 1)[0]
    return slug.replace("-", " ").strip().title() or "Oferta Fundación Adecco"


def _strip_location_suffix(title: str) -> str:
    return re.sub(r"\s+en\s+[A-Za-zÀ-ÿ /.-]+$", "", title).strip()


def _location_from_details(details: str | None) -> str | None:
    if details is None:
        return None
    cleaned = _clean_text(details)
    if cleaned is None:
        return None
    match = re.match(r"(?P<location>[A-Za-zÀ-ÿ /.-]+)\s+Publicada:", cleaned)
    if match:
        return match.group("location").strip()
    return None


def _detail_location(soup: BeautifulSoup) -> str | None:
    for subsection in soup.select(".job-info-paragraph-subsection"):
        if not isinstance(subsection, Tag):
            continue
        heading = _text(subsection.select_one("h3"))
        if heading and _fold_text(heading) == "ubicacion":
            paragraph = _text(subsection.select_one("p"))
            if paragraph:
                return paragraph
    return None


def _publication_date(text: str | None) -> datetime | None:
    if text is None:
        return None
    match = re.search(r"Publicada:\s*(?P<date>\d{2}/\d{2}/\d{4})", text)
    if match is None:
        return None
    try:
        parsed = datetime.strptime(match.group("date"), "%d/%m/%Y")
    except ValueError:
        return None
    return parsed.replace(tzinfo=UTC)


def _remote_type(text: str) -> RemoteType:
    folded = _fold_text(text)
    if any(token in folded for token in ("100% trabajo en remoto", "remoto", "teletrabajo")):
        return RemoteType.REMOTE
    if any(token in folded for token in ("hibrido", "hybrid")):
        return RemoteType.HYBRID
    if "presencial" in folded:
        return RemoteType.ONSITE
    return RemoteType.UNKNOWN


def _employment_type(text: str | None) -> str | None:
    if text is None:
        return None
    folded = _fold_text(text)
    if "tiempo completo" in folded or "jornada completa" in folded:
        return "full_time"
    if "parcial" in folded or "media jornada" in folded:
        return "part_time"
    return None


def _salary_text(text: str | None) -> str | None:
    if text is None:
        return None
    cleaned = _clean_text(text)
    if cleaned is None:
        return None
    folded = _fold_text(cleaned)
    if "salario segun experiencia" in folded:
        return "Salario según experiencia"
    if "salario competitivo" in folded:
        return "Salario competitivo"
    amount_match = re.search(
        r"(?:salario\s*)?\d[\d\s.,]*(?:€|eur|euros)(?:\s+al\s+\w+)?",
        cleaned,
        re.IGNORECASE,
    )
    if amount_match:
        return amount_match.group(0).strip()[:300]
    if "salario" in folded:
        start = max(0, folded.find("salario") - 40)
        return cleaned[start : start + 300].strip()
    return None


def _text(element: Tag | None) -> str | None:
    if element is None:
        return None
    return _clean_text(element.get_text(" ", strip=True))


def _clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    text = re.sub(r"\s+", " ", value.replace("\xa0", " ")).strip()
    return text or None


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
