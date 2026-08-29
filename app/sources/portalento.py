from __future__ import annotations

import asyncio
import json
import logging
import re
import unicodedata
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from typing import Any

import httpx
from bs4 import BeautifulSoup
from bs4.element import Tag

from app.core.config import get_settings
from app.models.enums import RemoteType
from app.sources.base import RawJob, SearchConfig

logger = logging.getLogger(__name__)


class PortalentoJobSource:
    name = "portalento"

    def __init__(self, settings: dict[str, Any]) -> None:
        self.enabled = bool(settings.get("enabled", True))
        self.base_url: str | None = str(settings.get("base_url", "https://www.portalento.es"))
        self.sitemap_url = str(
            settings.get("sitemap_url", "https://www.portalento.es/sitemap_ofertas.xml")
        )
        self.timeout_seconds = float(
            settings.get("timeout_seconds", get_settings().http_timeout_seconds)
        )
        self.retries = int(settings.get("retries", 2))
        self.rate_limit_seconds = float(settings.get("rate_limit_seconds", 1.5))
        self.min_interval_minutes = int(settings.get("min_interval_minutes", 360))
        self.minimum_score = int(settings.get("minimum_score", 35))
        self.max_jobs = int(settings.get("max_jobs", 20))
        self.max_detail_pages = int(settings.get("max_detail_pages", 25))
        self.strict_search_filter = bool(settings.get("strict_search_filter", True))
        self.url_required_any_keywords = _string_list(
            settings.get("url_required_any_keywords", [])
        )
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
            "Accept": "text/html,application/xhtml+xml,application/xml",
            "User-Agent": "JobRadar/0.1 (personal job research; source attribution kept)",
        }
        async with httpx.AsyncClient(
            timeout=self.timeout_seconds, headers=headers, follow_redirects=True
        ) as client:
            try:
                sitemap = await self._fetch_page(client, self.sitemap_url)
            except RuntimeError:
                logger.warning(
                    "No se pudo consultar el sitemap de Portalento",
                    extra={"source": self.name, "url": self.sitemap_url},
                )
                return []
            urls = _candidate_urls(
                sitemap,
                self.url_required_any_keywords,
                self.max_detail_pages,
            )
            jobs: list[RawJob] = []
            for url in urls:
                try:
                    payload = await self._fetch_page(client, url)
                except RuntimeError:
                    continue
                job = self._job_from_detail(payload, url)
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
                    "Fallo temporal consultando Portalento",
                    extra={"source": self.name, "url": url, "attempt": attempt + 1},
                )
                await asyncio.sleep(wait_seconds)
        msg = f"Portalento page failed after retries: {last_error}"
        raise RuntimeError(msg) from last_error

    def _job_from_detail(self, payload: str, url: str) -> RawJob | None:
        posting = _job_posting(payload)
        if not posting:
            return None
        soup = BeautifulSoup(payload, "html.parser")
        summary = _summary_fields(soup)
        title = _optional_str(posting.get("title")) or _title_from_url(url)
        description = _clean_text(str(posting.get("description") or "")) or title
        company_name = _organization_name(posting.get("hiringOrganization")) or _optional_str(
            summary.get("Empresa")
        )
        location = _location_from_posting(posting) or _optional_str(
            summary.get("Lugar de trabajo")
        )
        salary = _salary_from_summary(summary.get("Salario bruto"))
        posted_text = _optional_str(posting.get("datePosted")) or _optional_str(
            summary.get("Fecha publicación")
        )
        publication_date = _parse_date(posted_text)
        expiration_date = _parse_date(_optional_str(summary.get("Inscripción hasta")))
        combined = f"{title} {description} {location or ''}"
        requirements = " | ".join(
            part
            for part in (
                "Oferta publicada en portal de empleo para personas con discapacidad",
                _experience_text(description),
            )
            if part
        )
        return RawJob(
            source_name=self.name,
            source_job_id=_source_job_id(url),
            company_name=company_name or "Inserta Empleo",
            title=title,
            description=description,
            requirements=requirements,
            location=location,
            country="Spain",
            remote_type=_remote_type(combined),
            employment_type=_employment_type(_optional_str(summary.get("Duración jornada"))),
            salary_original_text=salary,
            url=url,
            publication_date=publication_date,
            expiration_date=expiration_date,
            raw_payload={"sitemap_url": self.sitemap_url, "summary": summary},
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


def _candidate_urls(
    sitemap_payload: str, url_required_any_keywords: list[str], max_detail_pages: int
) -> list[str]:
    urls = _sitemap_urls(sitemap_payload)
    if url_required_any_keywords:
        urls = [
            url
            for url in urls
            if any(
                _contains_keyword(url.replace("-", " "), keyword)
                for keyword in url_required_any_keywords
            )
        ]
    return urls[:max_detail_pages]


def _sitemap_urls(payload: str) -> list[str]:
    try:
        root = ET.fromstring(payload.lstrip("\ufeff"))
    except ET.ParseError:
        return re.findall(r"<loc>(.*?)</loc>", payload)
    urls: list[str] = []
    for element in root.iter():
        if element.tag.endswith("loc") and element.text:
            urls.append(element.text.strip())
    return urls


def _job_posting(payload: str) -> dict[str, Any] | None:
    soup = BeautifulSoup(payload, "html.parser")
    for script in soup.select('script[type="application/ld+json"]'):
        if not isinstance(script, Tag):
            continue
        try:
            data = json.loads(re.sub(r"[\r\n\t]+", " ", script.get_text(strip=True)))
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict) and data.get("@type") == "JobPosting":
            return data
    return None


def _summary_fields(soup: BeautifulSoup) -> dict[str, str]:
    fields: dict[str, str] = {}
    for paragraph in soup.select(".datosReferencia p"):
        if not isinstance(paragraph, Tag):
            continue
        label = paragraph.find("strong")
        if not isinstance(label, Tag):
            continue
        key = _clean_text(label.get_text(" ", strip=True).rstrip(":"))
        label_text = label.get_text(" ", strip=True)
        value = _clean_text(paragraph.get_text(" ", strip=True).replace(label_text, ""))
        if key and value:
            fields[key] = value
    return fields


def _organization_name(value: object) -> str | None:
    if isinstance(value, dict):
        return _optional_str(value.get("name"))
    return _optional_str(value)


def _location_from_posting(posting: dict[str, Any]) -> str | None:
    location = posting.get("jobLocation")
    if not isinstance(location, dict):
        return None
    address = location.get("address")
    if isinstance(address, dict):
        return ", ".join(
            part
            for part in (
                _optional_str(address.get("addressLocality")),
                _optional_str(address.get("addressRegion")),
                _optional_str(address.get("addressCountry")),
            )
            if part
        ) or None
    return _optional_str(address)


def _salary_from_summary(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = _clean_text(value)
    if cleaned is None:
        return None
    match = re.search(
        r"(?:entre\s*)?(?P<min>\d[\d.]*)\s*€\s*(?:y|-|a|hasta)\s*(?P<max>\d[\d.]*)\s*€",
        cleaned,
        re.IGNORECASE,
    )
    if match:
        return f"{match.group('min').replace('.', '')}-{match.group('max').replace('.', '')} EUR"
    single = re.search(r"(?P<amount>\d[\d.]*)\s*€", cleaned, re.IGNORECASE)
    if single:
        return f"{single.group('amount').replace('.', '')} EUR"
    if "salario" in _fold_text(cleaned):
        return cleaned[:250]
    return None


def _source_job_id(url: str) -> str:
    return url.rstrip("/").rsplit("/", 1)[-1]


def _title_from_url(url: str) -> str:
    parts = url.rstrip("/").split("/")
    if len(parts) >= 2:
        return parts[-2].replace("-", " ").title()
    return "Oferta Por Talento"


def _experience_text(text: str) -> str | None:
    match = re.search(
        r"(?:(?:experiencia\s+(?:laboral\s*)?)|(?:al menos\s*))(?P<years>\d{1,2})\s*(?:años|anos)",
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
    if "40" in folded or "completa" in folded:
        return "full_time"
    if "parcial" in folded or "20" in folded:
        return "part_time"
    return None


def _remote_type(text: str) -> RemoteType:
    folded = _fold_text(text)
    if any(token in folded for token in ("remoto", "teletrabajo", "remote")):
        return RemoteType.REMOTE
    if any(token in folded for token in ("hibrido", "hybrid")):
        return RemoteType.HYBRID
    return RemoteType.UNKNOWN


def _parse_date(value: str | None) -> datetime | None:
    if value is None:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            parsed = datetime.strptime(value, fmt)
        except ValueError:
            continue
        return parsed.replace(tzinfo=UTC)
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
