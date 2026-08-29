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
class ManpowerPage:
    url: str
    location_hint: str | None
    country: str | None


class ManpowerJobSource:
    name = "manpower"

    def __init__(self, settings: dict[str, Any]) -> None:
        self.enabled = bool(settings.get("enabled", True))
        self.base_url: str | None = str(settings.get("base_url", "https://www.manpower.es"))
        self.pages = _page_list(settings.get("pages", []))
        self.timeout_seconds = float(
            settings.get("timeout_seconds", get_settings().http_timeout_seconds)
        )
        self.retries = int(settings.get("retries", 2))
        self.rate_limit_seconds = float(settings.get("rate_limit_seconds", 1))
        self.detail_rate_limit_seconds = float(settings.get("detail_rate_limit_seconds", 0.5))
        self.min_interval_minutes = int(settings.get("min_interval_minutes", 360))
        self.minimum_score = int(settings.get("minimum_score", 45))
        self.max_jobs = int(settings.get("max_jobs", 30))
        self.max_detail_pages = int(settings.get("max_detail_pages", 35))
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
        urls: list[tuple[str, ManpowerPage]] = []
        async with httpx.AsyncClient(
            timeout=self.timeout_seconds, headers=headers, follow_redirects=True
        ) as client:
            for page in self.pages:
                try:
                    payload = await self._fetch_page(client, page.url)
                except RuntimeError:
                    logger.warning(
                        "No se pudo consultar la pagina de Manpower",
                        extra={"source": self.name, "url": page.url},
                    )
                    continue
                urls.extend((url, page) for url in self._job_urls_from_html(payload))
                await asyncio.sleep(self.rate_limit_seconds)

            jobs: list[RawJob] = []
            for url, page in _dedupe_url_pages(urls)[: self.max_detail_pages]:
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
                    "Fallo temporal consultando Manpower",
                    extra={"source": self.name, "url": url, "attempt": attempt + 1},
                )
                await asyncio.sleep(wait_seconds)
        raise RuntimeError(f"Manpower page failed after retries: {last_error}") from last_error

    def _job_urls_from_html(self, payload: str) -> list[str]:
        soup = BeautifulSoup(payload, "html.parser")
        urls: list[str] = []
        for link in soup.select('a[href*="/es/empleos/"]'):
            if not isinstance(link, Tag):
                continue
            href = _optional_str(link.get("href"))
            if href is None:
                continue
            urls.append(urljoin(str(self.base_url), href))
        return _dedupe_strings(urls)

    def _job_from_detail_html(
        self, payload: str, url: str, page: ManpowerPage
    ) -> RawJob | None:
        soup = BeautifulSoup(payload, "html.parser")
        posting = _job_posting(soup)
        if posting is None:
            return None
        title = _optional_str(posting.get("title"))
        description = _html_to_text(_optional_str(posting.get("description")))
        if title is None or description is None:
            return None
        lines = _text_lines(soup)
        metadata = _metadata(lines)
        location = _posting_location(posting) or page.location_hint
        salary = metadata.get("salario") or _base_salary_text(posting.get("baseSalary"))
        requirements = _requirements(metadata)
        combined = " ".join(
            part
            for part in (
                title,
                description,
                requirements or "",
                location or "",
                salary or "",
            )
            if part
        )
        return RawJob(
            source_name=self.name,
            source_job_id=_source_job_id(url),
            company_name=_posting_company(posting) or metadata.get("nombre de la compania")
            or "Manpower",
            title=title.rstrip("."),
            description=description,
            requirements=requirements,
            location=_with_location_hint(location, page.location_hint),
            country=page.country,
            remote_type=_remote_type(combined),
            employment_type=metadata.get("tipo de empleo"),
            salary_original_text=salary,
            url=url,
            publication_date=_parse_date(_optional_str(posting.get("datePosted"))),
            expiration_date=_parse_date(_optional_str(posting.get("validThrough"))),
            raw_payload={
                "page_url": page.url,
                "url": url,
                "metadata": metadata,
                "json_ld": posting,
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


def _job_posting(soup: BeautifulSoup) -> dict[str, Any] | None:
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


def _metadata(lines: list[str]) -> dict[str, str]:
    labels = {
        "numero de referencia": "numero de referencia",
        "tipo de empleo": "tipo de empleo",
        "salario": "salario",
        "sector": "sector",
        "experiencia": "experiencia",
        "nombre de la compania": "nombre de la compania",
    }
    metadata: dict[str, str] = {}
    for index, line in enumerate(lines[:-1]):
        folded = _fold_text(line).strip(" :")
        key = labels.get(folded)
        if key is None:
            continue
        value = lines[index + 1].strip()
        if value:
            metadata[key] = value
    return metadata


def _requirements(metadata: dict[str, str]) -> str | None:
    parts = []
    if metadata.get("experiencia"):
        parts.append(f"Experience: {metadata['experiencia']}")
    if metadata.get("tipo de empleo"):
        parts.append(f"Employment type: {metadata['tipo de empleo']}")
    if metadata.get("sector"):
        parts.append(f"Sector: {metadata['sector']}")
    return ". ".join(parts) or None


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


def _page_list(value: object) -> list[ManpowerPage]:
    if not isinstance(value, list):
        return []
    pages: list[ManpowerPage] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        url = _optional_str(item.get("url"))
        if url is None:
            continue
        pages.append(
            ManpowerPage(
                url=url,
                location_hint=_optional_str(item.get("location_hint")),
                country=_optional_str(item.get("country")) or "Spain",
            )
        )
    return pages


def _source_job_id(url: str) -> str:
    match = re.search(r"/(?P<id>\d+)(?:[/?#]|$)", url)
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


def _dedupe_url_pages(values: list[tuple[str, ManpowerPage]]) -> list[tuple[str, ManpowerPage]]:
    seen: set[str] = set()
    deduped: list[tuple[str, ManpowerPage]] = []
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


def _html_to_text(value: str | None) -> str | None:
    if value is None:
        return None
    return _clean_text(BeautifulSoup(value, "html.parser").get_text(" ", strip=True))


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
