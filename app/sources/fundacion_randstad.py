from __future__ import annotations

import asyncio
import logging
import re
import unicodedata
from datetime import UTC, datetime
from typing import Any

import httpx

from app.core.config import get_settings
from app.models.enums import RemoteType
from app.sources.base import RawJob, SearchConfig

logger = logging.getLogger(__name__)


class FundacionRandstadJobSource:
    name = "fundacion_randstad"

    def __init__(self, settings: dict[str, Any]) -> None:
        self.enabled = bool(settings.get("enabled", True))
        self.base_url: str | None = str(settings.get("base_url", "https://www.randstad.es"))
        self.api_url = str(
            settings.get("api_url", "https://apis.randstad.es/talent/offers/")
        )
        self.business_id = int(settings.get("business_id", 9))
        self.page_size = int(settings.get("page_size", 20))
        self.max_pages = int(settings.get("max_pages", 10))
        self.timeout_seconds = float(
            settings.get("timeout_seconds", get_settings().http_timeout_seconds)
        )
        self.retries = int(settings.get("retries", 2))
        self.rate_limit_seconds = float(settings.get("rate_limit_seconds", 1))
        self.min_interval_minutes = int(settings.get("min_interval_minutes", 360))
        self.minimum_score = int(settings.get("minimum_score", 35))
        self.max_jobs = int(settings.get("max_jobs", 30))
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
            "Accept": "application/json",
            "User-Agent": "JobRadar/0.1 (personal job research; source attribution kept)",
        }
        jobs: list[RawJob] = []
        async with httpx.AsyncClient(
            timeout=self.timeout_seconds, headers=headers, follow_redirects=True
        ) as client:
            for page in range(self.max_pages):
                try:
                    payload = await self._fetch_page(client, page)
                except RuntimeError:
                    logger.warning(
                        "No se pudo consultar la API de Fundacion Randstad",
                        extra={"source": self.name, "page": page},
                    )
                    break
                jobs.extend(
                    job
                    for item in payload.get("result", [])
                    if isinstance(item, dict)
                    if (job := self._to_raw_job(item)) is not None
                )
                pagination = payload.get("pagination")
                if not isinstance(pagination, dict) or not pagination.get("hasNext"):
                    break
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

    async def _fetch_page(self, client: httpx.AsyncClient, page: int) -> dict[str, Any]:
        last_error: Exception | None = None
        params = {
            "bussinessId": self.business_id,
            "page": page,
            "elements": self.page_size,
        }
        for attempt in range(self.retries + 1):
            try:
                response = await client.get(self.api_url, params=params)
                response.raise_for_status()
                data = response.json()
                if isinstance(data, dict):
                    return data
                raise ValueError("Randstad API returned a non-object payload")
            except (httpx.HTTPError, ValueError) as exc:
                last_error = exc
                wait_seconds = min(2**attempt, 8)
                logger.warning(
                    "Fallo temporal consultando Fundacion Randstad",
                    extra={"source": self.name, "page": page, "attempt": attempt + 1},
                )
                await asyncio.sleep(wait_seconds)
        msg = f"Fundacion Randstad API failed after retries: {last_error}"
        raise RuntimeError(msg) from last_error

    def _to_raw_job(self, item: dict[str, Any]) -> RawJob | None:
        title = _optional_str(item.get("title"))
        url = _optional_str(item.get("url"))
        offer_id = _optional_str(item.get("offerId"))
        if title is None or offer_id is None:
            return None
        description = _join_text(
            item.get("introduction"),
            item.get("description"),
            item.get("conditions"),
        )
        requirements = _join_text(
            _experience_requirement(item.get("experienceYears")),
            item.get("requirements"),
        )
        location = _location(item)
        combined = f"{title} {description} {requirements or ''} {location or ''}"
        modality = _optional_str((item.get("workModality") or {}).get("name"))
        journal_type = _optional_str((item.get("journalType") or {}).get("name"))
        return RawJob(
            source_name=self.name,
            source_job_id=offer_id,
            company_name=_optional_str(item.get("company"))
            or _optional_str(item.get("publicationCompanyBusiness"))
            or "Fundacion Randstad",
            title=title,
            description=description or title,
            requirements=requirements,
            location=location,
            country="Spain",
            remote_type=_remote_type(modality, combined),
            employment_type=_employment_type(journal_type),
            salary_original_text=_salary_text(item),
            url=url,
            publication_date=_parse_date(_optional_str(item.get("date"))),
            raw_payload={
                "sector": item.get("sector"),
                "functional_area": item.get("functionalArea"),
                "jobtype": item.get("jobtype"),
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


def _location(item: dict[str, Any]) -> str | None:
    city = item.get("city")
    province = item.get("province")
    parts = []
    if isinstance(city, dict):
        parts.append(_optional_str(city.get("name")))
    if isinstance(province, dict):
        parts.append(_optional_str(province.get("name")))
    return ", ".join(part for part in parts if part) or None


def _salary_text(item: dict[str, Any]) -> str | None:
    min_salary = _optional_int(item.get("minSalary"))
    max_salary = _optional_int(item.get("maxSalary"))
    salary_type = _optional_str(item.get("salarayTypeName"))
    period = _period_from_salary_type(salary_type)
    if min_salary is not None and max_salary is not None:
        return f"{min_salary}-{max_salary} EUR {period}"
    if min_salary is not None:
        return f"{min_salary} EUR {period}"
    conditions = _optional_str(item.get("conditions"))
    if conditions and "salario" in _fold_text(conditions):
        return conditions[:300]
    return None


def _period_from_salary_type(value: str | None) -> str:
    folded = _fold_text(value or "")
    if "mes" in folded:
        return "al mes"
    if "hora" in folded:
        return "por hora"
    if "dia" in folded:
        return "por dia"
    return "al año"


def _remote_type(modality: str | None, combined: str) -> RemoteType:
    folded = _fold_text(f"{modality or ''} {combined}")
    if any(token in folded for token in ("remoto", "teletrabajo", "remote")):
        return RemoteType.REMOTE
    if any(token in folded for token in ("combinada", "hibrido", "hybrid")):
        return RemoteType.HYBRID
    if "presencial" in folded:
        return RemoteType.ONSITE
    return RemoteType.UNKNOWN


def _employment_type(value: str | None) -> str | None:
    if value is None:
        return None
    folded = _fold_text(value)
    if "completa" in folded or "full" in folded:
        return "full_time"
    if "parcial" in folded or "part" in folded:
        return "part_time"
    return None


def _experience_requirement(value: object) -> str | None:
    years = _optional_int(value)
    if years is None or years <= 0:
        return None
    return f"Experiencia requerida: {years} años"


def _join_text(*parts: object) -> str | None:
    cleaned = [_optional_str(part) for part in parts]
    text = " ".join(part for part in cleaned if part)
    return re.sub(r"\s+", " ", text).strip() or None


def _parse_date(value: str | None) -> datetime | None:
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
