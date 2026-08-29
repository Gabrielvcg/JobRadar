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
class BizneoPage:
    url: str
    location_hint: str | None
    country: str | None


class BizneoJobSource:
    name = "bizneo"

    def __init__(self, settings: dict[str, Any]) -> None:
        self.enabled = bool(settings.get("enabled", True))
        self.base_url: str | None = _optional_str(settings.get("base_url"))
        self.company_name = _optional_str(settings.get("company_name")) or "Unknown company"
        self.pages = _page_list(settings.get("pages", []))
        self.timeout_seconds = float(
            settings.get("timeout_seconds", get_settings().http_timeout_seconds)
        )
        self.retries = int(settings.get("retries", 2))
        self.rate_limit_seconds = float(settings.get("rate_limit_seconds", 1))
        self.detail_rate_limit_seconds = float(settings.get("detail_rate_limit_seconds", 0.5))
        self.min_interval_minutes = int(settings.get("min_interval_minutes", 360))
        self.minimum_score = int(settings.get("minimum_score", 45))
        self.max_jobs = int(settings.get("max_jobs", 40))
        self.max_detail_pages = int(settings.get("max_detail_pages", 40))
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
        url_pages: list[tuple[str, BizneoPage]] = []
        async with httpx.AsyncClient(
            timeout=self.timeout_seconds, headers=headers, follow_redirects=True
        ) as client:
            for page in self.pages:
                try:
                    payload = await self._fetch_page(client, page.url)
                except RuntimeError:
                    logger.warning(
                        "No se pudo consultar la pagina de Bizneo",
                        extra={"source": self.name, "url": page.url},
                    )
                    continue
                url_pages.extend((url, page) for url in self._job_urls_from_html(payload))
                await asyncio.sleep(self.rate_limit_seconds)

            jobs: list[RawJob] = []
            for url, page in _dedupe_url_pages(url_pages)[: self.max_detail_pages]:
                try:
                    payload = await self._fetch_page(client, url)
                except RuntimeError:
                    continue
                job = self._job_from_detail_html(payload, url, page)
                if job is not None:
                    jobs.append(job)
                await asyncio.sleep(self.detail_rate_limit_seconds)

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
                    "Fallo temporal consultando Bizneo",
                    extra={"source": self.name, "url": url, "attempt": attempt + 1},
                )
                await asyncio.sleep(wait_seconds)
        raise RuntimeError(f"Bizneo page failed after retries: {last_error}") from last_error

    def _job_urls_from_html(self, payload: str) -> list[str]:
        soup = BeautifulSoup(payload, "html.parser")
        urls: list[str] = []
        for link in soup.select('a.job-card[href*="/jobs/"]'):
            if not isinstance(link, Tag):
                continue
            href = _optional_str(link.get("href"))
            if href is None:
                continue
            urls.append(urljoin(str(self.base_url), href))
        return _dedupe_strings(urls)

    def _job_from_detail_html(self, payload: str, url: str, page: BizneoPage) -> RawJob | None:
        soup = BeautifulSoup(payload, "html.parser")
        title = _text(soup.select_one("h1"))
        if title is None:
            return None
        lines = _text_lines(soup)
        metadata = _metadata(lines)
        description = _description_after_title(lines, title)
        requirements = _requirements_after_heading(lines, "Requisitos minimos")
        if not description:
            description = title
        location = metadata.get("ubicacion") or page.location_hint
        combined = " ".join(
            part
            for part in (
                title,
                description,
                requirements or "",
                location or "",
                " ".join(metadata.values()),
            )
            if part
        )
        return RawJob(
            source_name=self.name,
            source_job_id=_source_job_id(url),
            company_name=self.company_name,
            title=title.rstrip("."),
            description=description,
            requirements=requirements or _requirements_from_metadata(metadata),
            location=_with_location_hint(location, page.location_hint),
            country=page.country,
            remote_type=_remote_type(metadata.get("modalidad de trabajo") or combined),
            employment_type=_employment_type(metadata.get("jornada laboral")),
            salary_original_text=_salary_from_lines(lines) or _salary_text(combined),
            url=url,
            publication_date=_publication_date(lines),
            raw_payload={
                "page_url": page.url,
                "url": url,
                "metadata": metadata,
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


def _page_list(value: object) -> list[BizneoPage]:
    if not isinstance(value, list):
        return []
    pages: list[BizneoPage] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        url = _optional_str(item.get("url"))
        if url is None:
            continue
        pages.append(
            BizneoPage(
                url=url,
                location_hint=_optional_str(item.get("location_hint")),
                country=_optional_str(item.get("country")) or "Spain",
            )
        )
    return pages


def _metadata(lines: list[str]) -> dict[str, str]:
    labels = {
        "ubicacion": "ubicacion",
        "categoria": "categoria",
        "subcategoria": "subcategoria",
        "sector": "sector",
        "jornada laboral": "jornada laboral",
        "modalidad de trabajo": "modalidad de trabajo",
        "nivel profesional": "nivel profesional",
        "departamento": "departamento",
    }
    metadata: dict[str, str] = {}
    for index, line in enumerate(lines[:-1]):
        key = labels.get(_fold_text(line).strip(" :"))
        if key is None:
            continue
        value = lines[index + 1].strip()
        if value:
            metadata[key] = value
    return metadata


def _description_after_title(lines: list[str], title: str) -> str:
    title_indexes = [
        index for index, line in enumerate(lines) if _fold_text(line) == _fold_text(title)
    ]
    start = (title_indexes[-1] + 1) if title_indexes else 0
    stop_markers = {
        "requisitos minimos",
        "competencias",
        "aplica ahora",
        "un segundo! queremos llevarte al lugar adecuado",
    }
    parts = []
    for line in lines[start:]:
        if _fold_text(line).strip(" :") in stop_markers:
            break
        parts.append(line)
    return _clean_text(" ".join(parts)) or title


def _requirements_after_heading(lines: list[str], heading: str) -> str | None:
    folded_heading = _fold_text(heading)
    start: int | None = None
    for index, line in enumerate(lines):
        if _fold_text(line).strip(" :") == folded_heading:
            start = index + 1
            break
    if start is None:
        return None
    stop_markers = {
        "competencias",
        "aplica ahora",
        "un segundo! queremos llevarte al lugar adecuado",
    }
    parts = []
    for line in lines[start:]:
        if _fold_text(line).strip(" :") in stop_markers:
            break
        parts.append(line)
    return _clean_text(" ".join(parts))


def _requirements_from_metadata(metadata: dict[str, str]) -> str | None:
    parts = []
    for key in ("jornada laboral", "modalidad de trabajo", "nivel profesional", "departamento"):
        if metadata.get(key):
            parts.append(f"{key}: {metadata[key]}")
    return ". ".join(parts) or None


def _publication_date(lines: list[str]) -> datetime | None:
    months = {
        "enero": 1,
        "febrero": 2,
        "marzo": 3,
        "abril": 4,
        "mayo": 5,
        "junio": 6,
        "julio": 7,
        "agosto": 8,
        "septiembre": 9,
        "setiembre": 9,
        "octubre": 10,
        "noviembre": 11,
        "diciembre": 12,
    }
    for line in lines[:20]:
        match = re.fullmatch(r"(\d{1,2})\s+de\s+([a-zA-Z]+)", _fold_text(line))
        if not match:
            continue
        day = int(match.group(1))
        month = months.get(match.group(2))
        if month is None:
            continue
        now = datetime.now(UTC)
        year = now.year if (month, day) <= (now.month, now.day) else now.year - 1
        return datetime(year, month, day, tzinfo=UTC)
    return None


def _source_job_id(url: str) -> str:
    return url.rstrip("/").rsplit("/", 1)[-1]


def _remote_type(text: str) -> RemoteType:
    folded = _fold_text(text)
    if any(token in folded for token in ("teletrabajo", "remoto", "remote")):
        return RemoteType.REMOTE
    if any(token in folded for token in ("hibrido", "hybrid")):
        return RemoteType.HYBRID
    if any(token in folded for token in ("presencial", "onsite")):
        return RemoteType.ONSITE
    return RemoteType.UNKNOWN


def _employment_type(value: str | None) -> str | None:
    if value is None:
        return None
    folded = _fold_text(value)
    if "completa" in folded:
        return "full_time"
    if "parcial" in folded or "25" in folded:
        return "part_time"
    return None


def _salary_text(text: str) -> str | None:
    match = re.search(
        r"(salario\s*(?:competitivo|acorde)?[^.|\n]{0,80}|"
        r"\d{1,3}(?:[.\s]\d{3})*(?:,\d+)?\s*(?:€|eur|euros?)"
        r"(?:\s*(?:-|a|to)\s*\d{1,3}(?:[.\s]\d{3})*(?:,\d+)?\s*(?:€|eur|euros?)?)?"
        r"(?:\s*(?:brutos?|bruto)?\s*/?\s*(?:hora|mes|año|ano|year|month|hour))?)",
        text,
        re.IGNORECASE,
    )
    if match is None:
        return None
    value = _clean_text(match.group(1))
    if value and _fold_text(value) == "salario competitivo acorde":
        return None
    return value


def _salary_from_lines(lines: list[str]) -> str | None:
    for line in lines:
        if "salario" in _fold_text(line):
            return _clean_text(line.lstrip("- "))
    return None


def _with_location_hint(location: str | None, hint: str | None) -> str | None:
    if location is None or hint is None:
        return location
    if _contains_keyword(location, hint):
        return location
    return f"{location}, {hint}"


def _dedupe_url_pages(values: list[tuple[str, BizneoPage]]) -> list[tuple[str, BizneoPage]]:
    seen: set[str] = set()
    deduped: list[tuple[str, BizneoPage]] = []
    for url, page in values:
        if url in seen:
            continue
        seen.add(url)
        deduped.append((url, page))
    return deduped


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


def _dedupe_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        deduped.append(value)
    return deduped


def _text_lines(soup: BeautifulSoup) -> list[str]:
    return [
        line
        for raw_line in soup.get_text("\n", strip=True).splitlines()
        for line in [_clean_text(raw_line)]
        if line
    ]


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
