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
class TecnoempleoPage:
    url: str
    location_hint: str | None
    country: str | None


class TecnoempleoJobSource:
    name = "tecnoempleo"

    def __init__(self, settings: dict[str, Any]) -> None:
        self.enabled = bool(settings.get("enabled", True))
        self.base_url: str | None = str(settings.get("base_url", "https://www.tecnoempleo.com"))
        self.pages = _page_list(settings.get("pages", []))
        self.timeout_seconds = float(
            settings.get("timeout_seconds", get_settings().http_timeout_seconds)
        )
        self.retries = int(settings.get("retries", 2))
        self.rate_limit_seconds = float(settings.get("rate_limit_seconds", 2))
        self.detail_rate_limit_seconds = float(settings.get("detail_rate_limit_seconds", 1))
        self.min_interval_minutes = int(settings.get("min_interval_minutes", 360))
        self.minimum_score = int(settings.get("minimum_score", 40))
        self.max_jobs = int(settings.get("max_jobs", 50))
        self.max_detail_pages = int(settings.get("max_detail_pages", 35))
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
                        "No se pudo consultar la pagina de Tecnoempleo",
                        extra={"source": self.name, "url": page.url},
                    )
                    continue
                jobs.extend(self._jobs_from_listing(payload, page))
                await asyncio.sleep(self.rate_limit_seconds)
            jobs = _dedupe_jobs(jobs)
            if self.enrich_details:
                jobs = await self._enrich_jobs(client, jobs[: self.max_detail_pages])

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
                    "Fallo temporal consultando Tecnoempleo",
                    extra={"source": self.name, "url": url, "attempt": attempt + 1},
                )
                await asyncio.sleep(wait_seconds)
        msg = f"Tecnoempleo page failed after retries: {last_error}"
        raise RuntimeError(msg) from last_error

    def _jobs_from_listing(self, payload: str, page: TecnoempleoPage) -> list[RawJob]:
        soup = BeautifulSoup(payload, "html.parser")
        return [
            job
            for job in (
                self._to_raw_job(card, page)
                for card in soup.select("div.p-3.border.rounded.mb-3.bg-white")
            )
            if job is not None
        ]

    def _to_raw_job(self, card: Tag, page: TecnoempleoPage) -> RawJob | None:
        link = card.select_one("h3 a[href]")
        if not isinstance(link, Tag):
            return None
        title = _clean_text(link.get_text(" ", strip=True))
        href = _optional_str(link.get("href"))
        if title is None or href is None:
            return None
        url = urljoin(str(self.base_url), href)
        company = _company_from_card(card) or "Tecnoempleo"
        listing_meta = _text(card.select_one(".d-block.d-lg-none.text-gray-800"))
        description = _listing_description(card) or title
        technologies = [
            text
            for badge in card.select(".badge")
            if (text := _clean_text(badge.get_text(" ", strip=True)))
        ]
        combined = " ".join(
            part
            for part in (
                title,
                description,
                listing_meta or "",
                " ".join(technologies),
            )
            if part
        )
        return RawJob(
            source_name=self.name,
            source_job_id=_source_job_id(url),
            company_name=company,
            title=title,
            description=description,
            requirements=", ".join(technologies) or None,
            location=_location_from_listing_meta(listing_meta) or page.location_hint,
            country=page.country,
            remote_type=_remote_type(combined),
            salary_original_text=_salary_from_listing_meta(listing_meta),
            url=url,
            publication_date=_date_from_listing_meta(listing_meta),
            raw_payload={
                "page_url": page.url,
                "title": title,
                "listing_meta": listing_meta,
                "technologies": technologies,
            },
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
    posting = _job_posting(payload)
    if not posting:
        return job
    title = _optional_str(posting.get("title")) or job.title
    description = _clean_text(str(posting.get("description") or "")) or job.description
    organization = posting.get("hiringOrganization")
    company_name = job.company_name
    if isinstance(organization, dict):
        company_name = _optional_str(organization.get("name")) or company_name
    location = _location_from_posting(posting) or job.location
    salary = _salary_from_posting(posting) or job.salary_original_text
    publication_date = _parse_iso_date(_optional_str(posting.get("datePosted")))
    requirements = _merge_requirements(job.requirements, description)
    combined = f"{title} {description} {requirements or ''} {location or ''}"
    remote_type = _remote_type(combined)
    if remote_type == RemoteType.UNKNOWN:
        remote_type = job.remote_type
    return RawJob(
        source_name=job.source_name,
        source_job_id=job.source_job_id,
        company_name=company_name,
        title=title,
        description=description,
        requirements=requirements,
        location=location,
        country=job.country,
        remote_type=remote_type,
        employment_type=_employment_type(_optional_str(posting.get("employmentType"))),
        salary_original_text=salary,
        url=job.url,
        publication_date=publication_date or job.publication_date,
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


def _job_posting(payload: str) -> dict[str, Any] | None:
    soup = BeautifulSoup(payload, "html.parser")
    for script in soup.select('script[type="application/ld+json"]'):
        if not isinstance(script, Tag):
            continue
        try:
            data = json.loads(script.get_text(strip=True))
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict) and data.get("@type") == "JobPosting":
            return data
    return None


def _company_from_card(card: Tag) -> str | None:
    for link in card.select("h3 + a, a.text-primary.link-muted"):
        if not isinstance(link, Tag):
            continue
        text = _clean_text(link.get_text(" ", strip=True))
        if text:
            return text
    return None


def _listing_description(card: Tag) -> str | None:
    block = card.select_one(".hidden-md-down.text-gray-800")
    if not isinstance(block, Tag):
        return None
    for badge in block.select(".badge"):
        badge.decompose()
    return _text(block)


def _location_from_listing_meta(text: str | None) -> str | None:
    if text is None:
        return None
    first_line = text.split(" - ", 1)[0]
    return _clean_text(first_line)


def _salary_from_listing_meta(text: str | None) -> str | None:
    if text is None:
        return None
    match = re.search(
        r"\d[\d.]*\s*€\s*-\s*\d[\d.]*\s*€\s*b/a|\d[\d.]*\s*€",
        text,
        re.IGNORECASE,
    )
    if not match:
        return None
    return match.group(0).replace("€", " EUR").replace("b/a", "al año")


def _date_from_listing_meta(text: str | None) -> datetime | None:
    if text is None:
        return None
    match = re.search(r"(?P<date>\d{2}/\d{2}/\d{4})", text)
    if match is None:
        return None
    try:
        parsed = datetime.strptime(match.group("date"), "%d/%m/%Y")
    except ValueError:
        return None
    return parsed.replace(tzinfo=UTC)


def _location_from_posting(posting: dict[str, Any]) -> str | None:
    location = posting.get("jobLocation")
    if isinstance(location, list):
        locations = [_location_from_place(item) for item in location if isinstance(item, dict)]
        return ", ".join(item for item in locations if item) or None
    if isinstance(location, dict):
        return _location_from_place(location)
    return None


def _location_from_place(place: dict[str, Any]) -> str | None:
    address = place.get("address")
    if isinstance(address, dict):
        parts = [
            _optional_str(address.get("addressLocality")),
            _optional_str(address.get("addressRegion")),
            _optional_str(address.get("addressCountry")),
        ]
        return ", ".join(part for part in parts if part)
    return _optional_str(address)


def _salary_from_posting(posting: dict[str, Any]) -> str | None:
    salary = posting.get("baseSalary")
    if not isinstance(salary, dict):
        return None
    currency = _optional_str(salary.get("currency")) or "EUR"
    value = salary.get("value")
    if not isinstance(value, dict):
        return None
    min_value = _optional_int(value.get("minValue"))
    max_value = _optional_int(value.get("maxValue"))
    single_value = _optional_int(value.get("value"))
    unit = _optional_str(value.get("unitText")) or "YEAR"
    period = _period_from_unit(unit)
    if min_value is not None and max_value is not None:
        return f"{min_value}-{max_value} {currency} {period}"
    if single_value is not None:
        return f"{single_value} {currency} {period}"
    return None


def _period_from_unit(unit: str) -> str:
    folded = _fold_text(unit)
    if folded in {"month", "mes"}:
        return "al mes"
    if folded in {"hour", "hora"}:
        return "por hora"
    if folded in {"day", "dia"}:
        return "por dia"
    return "al año"


def _merge_requirements(current: str | None, description: str) -> str | None:
    pieces = [current] if current else []
    experience = _experience_text(description)
    if experience:
        pieces.append(experience)
    return " | ".join(piece for piece in pieces if piece) or None


def _experience_text(text: str) -> str | None:
    match = re.search(
        r"(?:(?:experiencia\s+(?:requerida|mínima|minima)[:\s]*)|(?:al menos\s*))"
        r"(?P<years>\d{1,2})\s*(?:años|anos)",
        text,
        re.IGNORECASE,
    )
    if match:
        return f"Experiencia requerida: {match.group('years')} años"
    return None


def _employment_type(value: str | None) -> str | None:
    if value is None:
        return None
    folded = _fold_text(value)
    if "full_time" in folded or "jornada completa" in folded:
        return "full_time"
    if "part_time" in folded or "parcial" in folded:
        return "part_time"
    return None


def _page_list(value: object) -> list[TecnoempleoPage]:
    if not isinstance(value, list):
        return []
    pages: list[TecnoempleoPage] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        url = _optional_str(item.get("url"))
        if url is None:
            continue
        pages.append(
            TecnoempleoPage(
                url=url,
                location_hint=_optional_str(item.get("location_hint")),
                country=_optional_str(item.get("country")) or "Spain",
            )
        )
    return pages


def _source_job_id(url: str) -> str:
    match = re.search(r"/(?P<id>rf-[^/?#]+)", url)
    if match:
        return match.group("id")
    return url.rstrip("/").rsplit("/", 1)[-1]


def _remote_type(text: str) -> RemoteType:
    folded = _fold_text(text)
    if any(token in folded for token in ("100% remoto", "remoto", "teletrabajo", "remote")):
        return RemoteType.REMOTE
    if any(token in folded for token in ("hibrido", "hybrid")):
        return RemoteType.HYBRID
    if "presencial" in folded:
        return RemoteType.ONSITE
    return RemoteType.UNKNOWN


def _parse_iso_date(value: str | None) -> datetime | None:
    if value is None:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed


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
    text = re.sub(r"\s+", " ", value.replace("\xa0", " ")).strip()
    return text or None


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _optional_int(value: object) -> int | None:
    if value in (None, ""):
        return None
    try:
        number = float(str(value).replace(",", "."))
    except ValueError:
        return None
    if number <= 0:
        return None
    return int(round(number))


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
