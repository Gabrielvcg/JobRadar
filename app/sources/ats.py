from __future__ import annotations

import asyncio
import logging
import re
import xml.etree.ElementTree as ET
from collections.abc import Iterable
from datetime import UTC, datetime
from difflib import SequenceMatcher
from typing import Any

import httpx

from app.core.config import get_settings
from app.models.enums import RemoteType
from app.sources.base import RawJob, SearchConfig

logger = logging.getLogger(__name__)


class GreenhouseJobSource:
    name = "greenhouse_curated"

    def __init__(self, settings: dict[str, Any]) -> None:
        self.enabled = bool(settings.get("enabled", True))
        self.base_url: str | None = str(
            settings.get("base_url", "https://boards-api.greenhouse.io")
        )
        self.timeout_seconds = float(
            settings.get("timeout_seconds", get_settings().http_timeout_seconds)
        )
        self.retries = int(settings.get("retries", 2))
        self.min_interval_minutes = int(settings.get("min_interval_minutes", 360))
        self.minimum_score = int(settings.get("minimum_score", 35))
        self.rate_limit_seconds = float(settings.get("rate_limit_seconds", 1))
        self.companies = _company_settings(settings.get("companies", []))
        self.must_have_any_keywords = _string_list(settings.get("must_have_any_keywords", []))
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
        jobs_by_id: dict[str, RawJob] = {}
        async with httpx.AsyncClient(
            timeout=self.timeout_seconds, headers=headers, follow_redirects=True
        ) as client:
            for index, company in enumerate(self.companies):
                payload = await self._fetch_payload(client, company)
                for item in _greenhouse_items(payload):
                    job = self._to_raw_job(item, company)
                    key = job.source_job_id or job.url or f"{job.company_name}:{job.title}"
                    jobs_by_id[key] = job
                if index < len(self.companies) - 1:
                    await asyncio.sleep(self.rate_limit_seconds)
        return _filtered_jobs(
            jobs_by_id.values(),
            search_config,
            self.required_any_keywords,
            self.title_required_any_keywords,
            self.excluded_keywords,
            self.allowed_location_keywords,
            self.must_have_any_keywords,
        )

    async def _fetch_payload(
        self, client: httpx.AsyncClient, company: CompanySetting
    ) -> dict[str, Any]:
        url = f"{str(self.base_url).rstrip('/')}/v1/boards/{company.slug}/jobs"
        params = {"content": "true"}
        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                response = await client.get(url, params=params)
                if response.status_code == httpx.codes.NOT_FOUND:
                    logger.warning(
                        "Fuente Greenhouse sin feed publico",
                        extra={"source": self.name, "company": company.slug},
                    )
                    return {}
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, dict):
                    msg = "Greenhouse API returned a non-object JSON payload"
                    raise ValueError(msg)
                return payload
            except (httpx.HTTPError, ValueError) as exc:
                last_error = exc
                logger.warning(
                    "Fallo temporal consultando Greenhouse",
                    extra={"source": self.name, "company": company.slug, "attempt": attempt + 1},
                )
                await asyncio.sleep(min(2**attempt, 8))
        raise RuntimeError(
            f"Greenhouse API failed for {company.slug}: {last_error}"
        ) from last_error

    def _to_raw_job(self, item: dict[str, Any], company: CompanySetting) -> RawJob:
        location = _location_name(item.get("location"))
        source_job_id = _optional_str(item.get("id")) or _optional_str(
            item.get("absolute_url")
        )
        return RawJob(
            source_name=self.name,
            source_job_id=f"{company.slug}:{source_job_id}",
            company_name=_optional_str(item.get("company_name")) or company.name,
            title=str(item.get("title") or "Untitled job"),
            description=str(item.get("content") or ""),
            requirements=_greenhouse_requirements(item),
            location=location,
            country=_country_from_location(location),
            remote_type=RemoteType.REMOTE if _looks_remote(location) else RemoteType.UNKNOWN,
            salary_original_text=None,
            url=_optional_str(item.get("absolute_url")),
            publication_date=_parse_datetime(item.get("first_published"))
            or _parse_datetime(item.get("updated_at")),
            raw_payload=dict(item),
        )


class LeverJobSource:
    name = "lever_curated"

    def __init__(self, settings: dict[str, Any]) -> None:
        self.enabled = bool(settings.get("enabled", True))
        self.base_url: str | None = str(settings.get("base_url", "https://api.lever.co"))
        self.timeout_seconds = float(
            settings.get("timeout_seconds", get_settings().http_timeout_seconds)
        )
        self.retries = int(settings.get("retries", 2))
        self.min_interval_minutes = int(settings.get("min_interval_minutes", 360))
        self.minimum_score = int(settings.get("minimum_score", 35))
        self.rate_limit_seconds = float(settings.get("rate_limit_seconds", 1))
        self.companies = _company_settings(settings.get("companies", []))
        self.must_have_any_keywords = _string_list(settings.get("must_have_any_keywords", []))
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
        jobs_by_id: dict[str, RawJob] = {}
        async with httpx.AsyncClient(
            timeout=self.timeout_seconds, headers=headers, follow_redirects=True
        ) as client:
            for index, company in enumerate(self.companies):
                items = await self._fetch_items(client, company)
                for item in items:
                    job = self._to_raw_job(item, company)
                    key = job.source_job_id or job.url or f"{job.company_name}:{job.title}"
                    jobs_by_id[key] = job
                if index < len(self.companies) - 1:
                    await asyncio.sleep(self.rate_limit_seconds)
        return _filtered_jobs(
            jobs_by_id.values(),
            search_config,
            self.required_any_keywords,
            self.title_required_any_keywords,
            self.excluded_keywords,
            self.allowed_location_keywords,
            self.must_have_any_keywords,
        )

    async def _fetch_items(
        self, client: httpx.AsyncClient, company: CompanySetting
    ) -> list[dict[str, Any]]:
        url = f"{str(self.base_url).rstrip('/')}/v0/postings/{company.slug}"
        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                response = await client.get(url, params={"mode": "json"})
                if response.status_code == httpx.codes.NOT_FOUND:
                    logger.warning(
                        "Fuente Lever sin feed publico",
                        extra={"source": self.name, "company": company.slug},
                    )
                    return []
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, list):
                    msg = "Lever API returned a non-list JSON payload"
                    raise ValueError(msg)
                return [item for item in payload if isinstance(item, dict)]
            except (httpx.HTTPError, ValueError) as exc:
                last_error = exc
                logger.warning(
                    "Fallo temporal consultando Lever",
                    extra={"source": self.name, "company": company.slug, "attempt": attempt + 1},
                )
                await asyncio.sleep(min(2**attempt, 8))
        raise RuntimeError(f"Lever API failed for {company.slug}: {last_error}") from last_error

    def _to_raw_job(self, item: dict[str, Any], company: CompanySetting) -> RawJob:
        raw_categories = item.get("categories")
        categories: dict[str, Any] = raw_categories if isinstance(raw_categories, dict) else {}
        location = _lever_location(categories)
        commitment = _optional_str(categories.get("commitment"))
        source_job_id = _optional_str(item.get("id")) or _optional_str(item.get("hostedUrl"))
        remote_hint = f"{location or ''} {commitment or ''}"
        return RawJob(
            source_name=self.name,
            source_job_id=f"{company.slug}:{source_job_id}",
            company_name=company.name,
            title=str(item.get("text") or "Untitled job"),
            description=_lever_description(item),
            requirements=_lever_requirements(categories),
            location=location,
            country=_country_from_location(location),
            remote_type=RemoteType.REMOTE if _looks_remote(remote_hint) else RemoteType.UNKNOWN,
            employment_type=commitment,
            salary_original_text=_optional_str(item.get("salaryRange")),
            url=_optional_str(item.get("hostedUrl")) or _optional_str(item.get("applyUrl")),
            publication_date=_timestamp_ms_to_datetime(item.get("createdAt")),
            raw_payload=dict(item),
        )


class AshbyJobSource:
    name = "ashby_curated"

    def __init__(self, settings: dict[str, Any]) -> None:
        self.enabled = bool(settings.get("enabled", True))
        self.base_url: str | None = str(
            settings.get("base_url", "https://api.ashbyhq.com")
        )
        self.timeout_seconds = float(
            settings.get("timeout_seconds", get_settings().http_timeout_seconds)
        )
        self.retries = int(settings.get("retries", 2))
        self.min_interval_minutes = int(settings.get("min_interval_minutes", 360))
        self.minimum_score = int(settings.get("minimum_score", 35))
        self.rate_limit_seconds = float(settings.get("rate_limit_seconds", 1))
        self.companies = _company_settings(settings.get("companies", []))
        self.must_have_any_keywords = _string_list(settings.get("must_have_any_keywords", []))
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
        jobs_by_id: dict[str, RawJob] = {}
        async with httpx.AsyncClient(
            timeout=self.timeout_seconds, headers=headers, follow_redirects=True
        ) as client:
            for index, company in enumerate(self.companies):
                payload = await self._fetch_payload(client, company)
                for item in _ashby_items(payload):
                    job = self._to_raw_job(item, company)
                    key = job.source_job_id or job.url or f"{job.company_name}:{job.title}"
                    jobs_by_id[key] = job
                if index < len(self.companies) - 1:
                    await asyncio.sleep(self.rate_limit_seconds)
        return _filtered_jobs(
            jobs_by_id.values(),
            search_config,
            self.required_any_keywords,
            self.title_required_any_keywords,
            self.excluded_keywords,
            self.allowed_location_keywords,
            self.must_have_any_keywords,
        )

    async def _fetch_payload(
        self, client: httpx.AsyncClient, company: CompanySetting
    ) -> dict[str, Any]:
        url = f"{str(self.base_url).rstrip('/')}/posting-api/job-board/{company.slug}"
        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                response = await client.get(url, params={"includeCompensation": "true"})
                if response.status_code == httpx.codes.NOT_FOUND:
                    logger.warning(
                        "Fuente Ashby sin feed publico",
                        extra={"source": self.name, "company": company.slug},
                    )
                    return {}
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, dict):
                    msg = "Ashby API returned a non-object JSON payload"
                    raise ValueError(msg)
                return payload
            except (httpx.HTTPError, ValueError) as exc:
                last_error = exc
                logger.warning(
                    "Fallo temporal consultando Ashby",
                    extra={"source": self.name, "company": company.slug, "attempt": attempt + 1},
                )
                await asyncio.sleep(min(2**attempt, 8))
        raise RuntimeError(f"Ashby API failed for {company.slug}: {last_error}") from last_error

    def _to_raw_job(self, item: dict[str, Any], company: CompanySetting) -> RawJob:
        location = _ashby_location(item)
        workplace_type = _optional_str(item.get("workplaceType"))
        is_remote = item.get("isRemote") is True or workplace_type == "Remote"
        source_job_id = _optional_str(item.get("jobUrl")) or _optional_str(item.get("title"))
        return RawJob(
            source_name=self.name,
            source_job_id=f"{company.slug}:{source_job_id}",
            company_name=company.name,
            title=str(item.get("title") or "Untitled job"),
            description=str(item.get("descriptionPlain") or item.get("descriptionHtml") or ""),
            requirements=_ashby_requirements(item),
            location=location,
            country=_country_from_location(location),
            remote_type=RemoteType.REMOTE if is_remote else RemoteType.UNKNOWN,
            employment_type=_optional_str(item.get("employmentType")),
            salary_original_text=_ashby_salary_text(item),
            url=_optional_str(item.get("jobUrl")) or _optional_str(item.get("applyUrl")),
            publication_date=_parse_datetime(item.get("publishedAt")),
            raw_payload=dict(item),
        )


class WorkableJobSource:
    name = "workable_curated"

    def __init__(self, settings: dict[str, Any]) -> None:
        self.enabled = bool(settings.get("enabled", True))
        self.base_url: str | None = str(settings.get("base_url", "https://apply.workable.com"))
        self.timeout_seconds = float(
            settings.get("timeout_seconds", get_settings().http_timeout_seconds)
        )
        self.retries = int(settings.get("retries", 2))
        self.min_interval_minutes = int(settings.get("min_interval_minutes", 360))
        self.minimum_score = int(settings.get("minimum_score", 35))
        self.rate_limit_seconds = float(settings.get("rate_limit_seconds", 1))
        self.companies = _company_settings(settings.get("companies", []))
        self.must_have_any_keywords = _string_list(settings.get("must_have_any_keywords", []))
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
        jobs_by_id: dict[str, RawJob] = {}
        async with httpx.AsyncClient(
            timeout=self.timeout_seconds, headers=headers, follow_redirects=True
        ) as client:
            for index, company in enumerate(self.companies):
                payload = await self._fetch_payload(client, company)
                for item in _workable_items(payload):
                    job = self._to_raw_job(item, company)
                    key = job.source_job_id or job.url or f"{job.company_name}:{job.title}"
                    jobs_by_id[key] = job
                if index < len(self.companies) - 1:
                    await asyncio.sleep(self.rate_limit_seconds)
        return _filtered_jobs(
            jobs_by_id.values(),
            search_config,
            self.required_any_keywords,
            self.title_required_any_keywords,
            self.excluded_keywords,
            self.allowed_location_keywords,
            self.must_have_any_keywords,
        )

    async def _fetch_payload(
        self, client: httpx.AsyncClient, company: CompanySetting
    ) -> dict[str, Any]:
        url = f"{str(self.base_url).rstrip('/')}/api/v1/widget/accounts/{company.slug}"
        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                response = await client.get(url)
                if response.status_code == httpx.codes.NOT_FOUND:
                    logger.warning(
                        "Fuente Workable sin feed publico",
                        extra={"source": self.name, "company": company.slug},
                    )
                    return {}
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, dict):
                    msg = "Workable API returned a non-object JSON payload"
                    raise ValueError(msg)
                return payload
            except (httpx.HTTPError, ValueError) as exc:
                last_error = exc
                logger.warning(
                    "Fallo temporal consultando Workable",
                    extra={"source": self.name, "company": company.slug, "attempt": attempt + 1},
                )
                await asyncio.sleep(min(2**attempt, 8))
        raise RuntimeError(f"Workable API failed for {company.slug}: {last_error}") from last_error

    def _to_raw_job(self, item: dict[str, Any], company: CompanySetting) -> RawJob:
        location = _workable_location(item)
        telecommuting = item.get("telecommuting") is True
        source_job_id = _optional_str(item.get("shortcode")) or _optional_str(item.get("url"))
        remote_type = (
            RemoteType.REMOTE
            if telecommuting or _looks_remote(location)
            else RemoteType.UNKNOWN
        )
        return RawJob(
            source_name=self.name,
            source_job_id=f"{company.slug}:{source_job_id}",
            company_name=company.name,
            title=str(item.get("title") or "Untitled job"),
            description=_workable_description(item),
            requirements=_workable_requirements(item),
            location=location,
            country=_country_from_location(location or _optional_str(item.get("country"))),
            remote_type=remote_type,
            employment_type=_optional_str(item.get("employment_type")),
            url=_optional_str(item.get("url")) or _optional_str(item.get("shortlink")),
            publication_date=_parse_datetime(item.get("published_on"))
            or _parse_datetime(item.get("created_at")),
            raw_payload=dict(item),
        )


class RecruiteeJobSource:
    name = "recruitee_curated"

    def __init__(self, settings: dict[str, Any]) -> None:
        self.enabled = bool(settings.get("enabled", True))
        self.base_url: str | None = str(
            settings.get("base_url", "https://{company}.recruitee.com")
        )
        self.timeout_seconds = float(
            settings.get("timeout_seconds", get_settings().http_timeout_seconds)
        )
        self.retries = int(settings.get("retries", 2))
        self.min_interval_minutes = int(settings.get("min_interval_minutes", 360))
        self.minimum_score = int(settings.get("minimum_score", 35))
        self.rate_limit_seconds = float(settings.get("rate_limit_seconds", 1))
        self.companies = _company_settings(settings.get("companies", []))
        self.must_have_any_keywords = _string_list(settings.get("must_have_any_keywords", []))
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
        jobs_by_id: dict[str, RawJob] = {}
        async with httpx.AsyncClient(
            timeout=self.timeout_seconds, headers=headers, follow_redirects=True
        ) as client:
            for index, company in enumerate(self.companies):
                payload = await self._fetch_payload(client, company)
                for item in _recruitee_items(payload):
                    job = self._to_raw_job(item, company)
                    key = job.source_job_id or job.url or f"{job.company_name}:{job.title}"
                    jobs_by_id[key] = job
                if index < len(self.companies) - 1:
                    await asyncio.sleep(self.rate_limit_seconds)
        return _filtered_jobs(
            jobs_by_id.values(),
            search_config,
            self.required_any_keywords,
            self.title_required_any_keywords,
            self.excluded_keywords,
            self.allowed_location_keywords,
            self.must_have_any_keywords,
        )

    async def _fetch_payload(
        self, client: httpx.AsyncClient, company: CompanySetting
    ) -> dict[str, Any]:
        url = f"{_company_base_url(self.base_url, company).rstrip('/')}/api/offers/"
        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                response = await client.get(url)
                if response.status_code == httpx.codes.NOT_FOUND:
                    logger.warning(
                        "Fuente Recruitee sin feed publico",
                        extra={"source": self.name, "company": company.slug},
                    )
                    return {}
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, dict):
                    msg = "Recruitee API returned a non-object JSON payload"
                    raise ValueError(msg)
                return payload
            except (httpx.HTTPError, ValueError) as exc:
                last_error = exc
                logger.warning(
                    "Fallo temporal consultando Recruitee",
                    extra={"source": self.name, "company": company.slug, "attempt": attempt + 1},
                )
                await asyncio.sleep(min(2**attempt, 8))
        raise RuntimeError(
            f"Recruitee API failed for {company.slug}: {last_error}"
        ) from last_error

    def _to_raw_job(self, item: dict[str, Any], company: CompanySetting) -> RawJob:
        location = _recruitee_location(item)
        source_job_id = _optional_str(item.get("id")) or _optional_str(item.get("slug"))
        remote_hint = f"{location or ''} {item.get('location') or ''}"
        remote_type = (
            RemoteType.REMOTE
            if item.get("remote") is True or _looks_remote(remote_hint)
            else RemoteType.UNKNOWN
        )
        return RawJob(
            source_name=self.name,
            source_job_id=f"{company.slug}:{source_job_id}",
            company_name=company.name,
            title=str(item.get("title") or "Untitled job"),
            description=_recruitee_description(item),
            requirements=_recruitee_requirements(item),
            location=location,
            country=_country_from_location(location),
            remote_type=remote_type,
            employment_type=_optional_str(item.get("employment_type")),
            url=_optional_str(item.get("careers_url"))
            or _optional_str(item.get("careers_apply_url")),
            publication_date=_parse_datetime(item.get("published_at"))
            or _parse_datetime(item.get("created_at")),
            raw_payload=dict(item),
        )


class PinpointJobSource:
    name = "pinpoint_curated"

    def __init__(self, settings: dict[str, Any]) -> None:
        self.enabled = bool(settings.get("enabled", True))
        self.base_url: str | None = str(
            settings.get("base_url", "https://{company}.pinpointhq.com")
        )
        self.timeout_seconds = float(
            settings.get("timeout_seconds", get_settings().http_timeout_seconds)
        )
        self.retries = int(settings.get("retries", 2))
        self.min_interval_minutes = int(settings.get("min_interval_minutes", 360))
        self.minimum_score = int(settings.get("minimum_score", 35))
        self.rate_limit_seconds = float(settings.get("rate_limit_seconds", 1))
        self.companies = _company_settings(settings.get("companies", []))
        self.must_have_any_keywords = _string_list(settings.get("must_have_any_keywords", []))
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
        jobs_by_id: dict[str, RawJob] = {}
        async with httpx.AsyncClient(
            timeout=self.timeout_seconds, headers=headers, follow_redirects=True
        ) as client:
            for index, company in enumerate(self.companies):
                payload = await self._fetch_payload(client, company)
                for item in _pinpoint_items(payload):
                    job = self._to_raw_job(item, company)
                    key = job.source_job_id or job.url or f"{job.company_name}:{job.title}"
                    jobs_by_id[key] = job
                if index < len(self.companies) - 1:
                    await asyncio.sleep(self.rate_limit_seconds)
        return _filtered_jobs(
            jobs_by_id.values(),
            search_config,
            self.required_any_keywords,
            self.title_required_any_keywords,
            self.excluded_keywords,
            self.allowed_location_keywords,
            self.must_have_any_keywords,
        )

    async def _fetch_payload(
        self, client: httpx.AsyncClient, company: CompanySetting
    ) -> object:
        url = f"{_company_base_url(self.base_url, company).rstrip('/')}/postings.json"
        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                response = await client.get(url)
                if response.status_code == httpx.codes.NOT_FOUND:
                    logger.warning(
                        "Fuente Pinpoint sin feed publico",
                        extra={"source": self.name, "company": company.slug},
                    )
                    return []
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, (dict, list)):
                    msg = "Pinpoint API returned an unexpected JSON payload"
                    raise ValueError(msg)
                return payload
            except (httpx.HTTPError, ValueError) as exc:
                last_error = exc
                logger.warning(
                    "Fallo temporal consultando Pinpoint",
                    extra={"source": self.name, "company": company.slug, "attempt": attempt + 1},
                )
                await asyncio.sleep(min(2**attempt, 8))
        raise RuntimeError(
            f"Pinpoint API failed for {company.slug}: {last_error}"
        ) from last_error

    def _to_raw_job(self, item: dict[str, Any], company: CompanySetting) -> RawJob:
        location = _pinpoint_location(item, company.location_hint)
        source_job_id = _optional_str(item.get("id")) or _optional_str(item.get("url"))
        workplace_type = _optional_str(item.get("workplace_type_text")) or _optional_str(
            item.get("workplace_type")
        )
        remote_type = (
            RemoteType.REMOTE
            if _looks_remote(f"{location or ''} {workplace_type or ''}")
            else RemoteType.UNKNOWN
        )
        return RawJob(
            source_name=self.name,
            source_job_id=f"{company.slug}:{source_job_id}",
            company_name=company.name,
            title=str(item.get("title") or "Untitled job"),
            description=_pinpoint_description(item),
            requirements=_pinpoint_requirements(item),
            location=location,
            country=_country_from_location(location),
            remote_type=remote_type,
            employment_type=_optional_str(item.get("employment_type_text"))
            or _optional_str(item.get("employment_type")),
            salary_original_text=_pinpoint_salary_text(item),
            url=_optional_str(item.get("url")),
            publication_date=_parse_datetime(item.get("published_at"))
            or _parse_datetime(item.get("created_at")),
            raw_payload=dict(item),
        )


class PersonioJobSource:
    name = "personio_curated"

    def __init__(self, settings: dict[str, Any]) -> None:
        self.enabled = bool(settings.get("enabled", True))
        self.base_url: str | None = str(
            settings.get("base_url", "https://{company}.jobs.personio.de")
        )
        self.language = str(settings.get("language", "en"))
        self.timeout_seconds = float(
            settings.get("timeout_seconds", get_settings().http_timeout_seconds)
        )
        self.retries = int(settings.get("retries", 2))
        self.min_interval_minutes = int(settings.get("min_interval_minutes", 360))
        self.minimum_score = int(settings.get("minimum_score", 35))
        self.rate_limit_seconds = float(settings.get("rate_limit_seconds", 1))
        self.companies = _company_settings(settings.get("companies", []))
        self.must_have_any_keywords = _string_list(settings.get("must_have_any_keywords", []))
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
            "Accept": "application/xml,text/xml",
            "User-Agent": "JobRadar/0.1 (personal job research; source attribution kept)",
        }
        jobs_by_id: dict[str, RawJob] = {}
        async with httpx.AsyncClient(
            timeout=self.timeout_seconds, headers=headers, follow_redirects=True
        ) as client:
            for index, company in enumerate(self.companies):
                payload = await self._fetch_payload(client, company)
                for item in _personio_items(payload):
                    job = self._to_raw_job(item, company)
                    key = job.source_job_id or job.url or f"{job.company_name}:{job.title}"
                    jobs_by_id[key] = job
                if index < len(self.companies) - 1:
                    await asyncio.sleep(self.rate_limit_seconds)
        return _filtered_jobs(
            jobs_by_id.values(),
            search_config,
            self.required_any_keywords,
            self.title_required_any_keywords,
            self.excluded_keywords,
            self.allowed_location_keywords,
            self.must_have_any_keywords,
        )

    async def _fetch_payload(
        self, client: httpx.AsyncClient, company: CompanySetting
    ) -> ET.Element | None:
        url = f"{_company_base_url(self.base_url, company).rstrip('/')}/xml"
        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                response = await client.get(url, params={"language": self.language})
                if response.status_code == httpx.codes.NOT_FOUND:
                    logger.warning(
                        "Fuente Personio sin feed publico",
                        extra={"source": self.name, "company": company.slug},
                    )
                    return None
                response.raise_for_status()
                return ET.fromstring(response.content)
            except (httpx.HTTPError, ET.ParseError) as exc:
                last_error = exc
                logger.warning(
                    "Fallo temporal consultando Personio",
                    extra={"source": self.name, "company": company.slug, "attempt": attempt + 1},
                )
                await asyncio.sleep(min(2**attempt, 8))
        raise RuntimeError(
            f"Personio XML feed failed for {company.slug}: {last_error}"
        ) from last_error

    def _to_raw_job(self, item: ET.Element, company: CompanySetting) -> RawJob:
        job_id = _personio_text(item, "id")
        location = _personio_location(item, company.location_hint)
        employment_type = _personio_text(item, "employmentType")
        years = _personio_text(item, "yearsOfExperience")
        remote_type = RemoteType.REMOTE if _looks_remote(location) else RemoteType.UNKNOWN
        return RawJob(
            source_name=self.name,
            source_job_id=f"{company.slug}:{job_id}",
            company_name=_personio_text(item, "subcompany") or company.name,
            title=_personio_text(item, "name") or "Untitled job",
            description=_personio_description(item),
            requirements=_personio_requirements(item, years),
            location=location,
            country=_country_from_location(location),
            remote_type=remote_type,
            employment_type=employment_type,
            salary_original_text=_personio_salary_text(item),
            url=_personio_url(item, company, self.language),
            publication_date=_parse_datetime(_personio_text(item, "createdAt")),
            raw_payload=_personio_payload(item),
        )


class CompanySetting:
    def __init__(self, slug: str, name: str, location_hint: str | None = None) -> None:
        self.slug = slug
        self.name = name
        self.location_hint = location_hint


def _filtered_jobs(
    jobs: Iterable[RawJob],
    search_config: SearchConfig,
    required_any_keywords: list[str],
    title_required_any_keywords: list[str],
    excluded_keywords: list[str],
    allowed_location_keywords: list[str],
    must_have_any_keywords: list[str],
) -> list[RawJob]:
    filtered = [
        job
        for job in jobs
        if _matches_affinity(
            job,
            search_config.queries,
            required_any_keywords,
            title_required_any_keywords,
            excluded_keywords,
            allowed_location_keywords,
            must_have_any_keywords,
        )
    ]
    return _dedupe_job_variants(filtered)


def _dedupe_job_variants(jobs: list[RawJob]) -> list[RawJob]:
    clusters: list[list[RawJob]] = []
    for job in jobs:
        for cluster in clusters:
            if _same_variant_family(cluster[0], job):
                cluster.append(job)
                break
        else:
            clusters.append([job])
    return [_best_variant(cluster) for cluster in clusters]


def _same_variant_family(first: RawJob, second: RawJob) -> bool:
    if _variant_key(first) != _variant_key(second):
        return False
    first_description = _description_fingerprint(first.description)
    second_description = _description_fingerprint(second.description)
    if not first_description or not second_description:
        return False
    return SequenceMatcher(None, first_description, second_description).ratio() >= 0.82


def _variant_key(job: RawJob) -> tuple[str, str, str]:
    return (
        job.source_name,
        _variant_text(job.company_name),
        _variant_text(job.title),
    )


def _description_fingerprint(value: str) -> str:
    text = re.sub(r"<[^>]+>", " ", value.lower())
    text = re.sub(r"\b(?:salary|compensation|base pay|pay range)\b", " ", text)
    text = re.sub(r"\b\d[\d,.\s]*(?:k|m)?\b", " ", text)
    text = re.sub(r"\b(?:eur|euro|euros|usd|gbp|pln|czk|sek|dkk|nok|chf)\b", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _variant_text(value: str | None) -> str:
    return re.sub(r"\s+", " ", (value or "").strip().lower())


def _best_variant(jobs: list[RawJob]) -> RawJob:
    return max(jobs, key=_variant_rank)


def _variant_rank(job: RawJob) -> tuple[int, float]:
    location = (job.location or "").lower()
    rank = 0
    if any(token in location for token in ("spain", "madrid", "barcelona")):
        rank += 50
    if any(token in location for token in ("europe", "emea", "us/eu", "eu remote")):
        rank += 45
    if any(token in location for token in ("worldwide", "global", "anywhere")):
        rank += 35
    if "remote" in location:
        rank += 10
    timestamp = job.publication_date.timestamp() if job.publication_date else 0.0
    return rank, timestamp


def _matches_affinity(
    job: RawJob,
    queries: list[str],
    required_any_keywords: list[str],
    title_required_any_keywords: list[str],
    excluded_keywords: list[str],
    allowed_location_keywords: list[str],
    must_have_any_keywords: list[str] | None = None,
) -> bool:
    title = job.title.lower()
    location = (job.location or "").lower()
    haystack = f"{job.title} {job.description} {job.requirements or ''}".lower()
    exclusion_text = f"{job.title} {job.requirements or ''}".lower()
    if allowed_location_keywords and location and not any(
        keyword.lower() in location for keyword in allowed_location_keywords
    ):
        return False
    if must_have_any_keywords and not any(
        _contains_keyword(haystack, keyword) for keyword in must_have_any_keywords
    ):
        return False
    if any(_contains_keyword(exclusion_text, keyword) for keyword in excluded_keywords):
        return False
    if title_required_any_keywords and not any(
        _contains_keyword(title, keyword) for keyword in title_required_any_keywords
    ):
        return False
    if required_any_keywords:
        return any(_contains_keyword(haystack, keyword) for keyword in required_any_keywords)
    return any(_contains_keyword(haystack, query) for query in queries)


def _greenhouse_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    jobs = payload.get("jobs", [])
    if not isinstance(jobs, list):
        return []
    return [item for item in jobs if isinstance(item, dict)]


def _ashby_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    jobs = payload.get("jobs", [])
    if not isinstance(jobs, list):
        return []
    return [item for item in jobs if isinstance(item, dict) and item.get("isListed") is not False]


def _workable_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    jobs = payload.get("jobs", [])
    if not isinstance(jobs, list):
        return []
    grouped: dict[str, dict[str, Any]] = {}
    for item in jobs:
        if not isinstance(item, dict):
            continue
        key = _optional_str(item.get("shortcode")) or _optional_str(item.get("url"))
        if not key:
            continue
        existing = grouped.setdefault(key, dict(item))
        locations = _workable_location_entries(existing)
        locations.extend(_workable_location_entries(item))
        existing["locations"] = _dedupe_locations(locations)
    return list(grouped.values())


def _recruitee_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    jobs = payload.get("offers", [])
    if not isinstance(jobs, list):
        return []
    return [item for item in jobs if isinstance(item, dict)]


def _pinpoint_items(payload: object) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []
    for key in ("postings", "data", "jobs"):
        jobs = payload.get(key)
        if isinstance(jobs, list):
            return [item for item in jobs if isinstance(item, dict)]
    return []


def _personio_items(payload: ET.Element | None) -> list[ET.Element]:
    if payload is None:
        return []
    return list(payload.iter("position"))


def _greenhouse_requirements(item: dict[str, Any]) -> str | None:
    fields = []
    for key in ("departments", "offices", "metadata"):
        value = item.get(key)
        if isinstance(value, list):
            fields.extend(_string_list_from_dicts(value))
    return ", ".join(fields) or None


def _ashby_location(item: dict[str, Any]) -> str | None:
    locations = [_optional_str(item.get("location"))]
    secondary = item.get("secondaryLocations")
    if isinstance(secondary, list):
        for entry in secondary:
            if isinstance(entry, dict):
                locations.append(_optional_str(entry.get("location")))
    return _bounded_text(", ".join(location for location in locations if location), 500) or None


def _ashby_requirements(item: dict[str, Any]) -> str | None:
    fields = [
        _optional_str(item.get("department")),
        _optional_str(item.get("team")),
        _optional_str(item.get("employmentType")),
        _optional_str(item.get("workplaceType")),
    ]
    return ", ".join(field for field in fields if field) or None


def _ashby_salary_text(item: dict[str, Any]) -> str | None:
    compensation = item.get("compensation")
    if not isinstance(compensation, dict):
        return None
    for key in ("scrapeableCompensationSalarySummary", "compensationTierSummary"):
        value = _optional_str(compensation.get(key))
        if value:
            return value
    return None


def _lever_description(item: dict[str, Any]) -> str:
    parts = [
        _optional_str(item.get("descriptionPlain")),
        _optional_str(item.get("additionalPlain")),
    ]
    lists = item.get("lists")
    if isinstance(lists, list):
        for block in lists:
            if isinstance(block, dict):
                parts.append(_optional_str(block.get("text")))
                parts.append(_optional_str(block.get("content")))
    return "\n\n".join(part for part in parts if part)


def _lever_location(categories: dict[str, Any]) -> str | None:
    locations = _string_list(categories.get("allLocations"))
    if locations:
        return _bounded_text(", ".join(locations), 500)
    return _optional_str(categories.get("location"))


def _lever_requirements(categories: dict[str, Any]) -> str | None:
    fields = [
        _optional_str(categories.get("department")),
        _optional_str(categories.get("team")),
        _optional_str(categories.get("commitment")),
    ]
    return ", ".join(part for part in fields if part) or None


def _workable_description(item: dict[str, Any]) -> str:
    parts = [
        _optional_str(item.get("title")),
        _optional_str(item.get("department")),
        _optional_str(item.get("function")),
        _optional_str(item.get("industry")),
        _optional_str(item.get("experience")),
        _workable_location(item),
    ]
    return "\n".join(part for part in parts if part)


def _workable_requirements(item: dict[str, Any]) -> str | None:
    fields = [
        _optional_str(item.get("department")),
        _optional_str(item.get("function")),
        _optional_str(item.get("industry")),
        _optional_str(item.get("employment_type")),
        _optional_str(item.get("experience")),
    ]
    return ", ".join(field for field in fields if field) or None


def _workable_location(item: dict[str, Any]) -> str | None:
    locations = _workable_location_entries(item)
    if not locations:
        city = _optional_str(item.get("city"))
        country = _optional_str(item.get("country"))
        locations = [", ".join(part for part in (city, country) if part)]
    return _bounded_text(", ".join(location for location in locations if location), 500) or None


def _workable_location_entries(item: dict[str, Any]) -> list[str]:
    locations = []
    raw_locations = item.get("locations")
    if isinstance(raw_locations, list):
        for entry in raw_locations:
            if not isinstance(entry, dict) or entry.get("hidden") is True:
                continue
            city = _optional_str(entry.get("city"))
            country = _optional_str(entry.get("country"))
            locations.append(", ".join(part for part in (city, country) if part))
    return [location for location in locations if location]


def _recruitee_description(item: dict[str, Any]) -> str:
    parts = [
        _optional_str(item.get("description")),
        _optional_str(item.get("benefits")),
        _optional_str(item.get("location")),
    ]
    return "\n\n".join(part for part in parts if part)


def _recruitee_requirements(item: dict[str, Any]) -> str | None:
    tags = item.get("tags")
    tag_text = ", ".join(_string_list(tags)) if isinstance(tags, list) else None
    fields = [
        _optional_str(item.get("requirements")),
        _optional_str(item.get("department")),
        _recruitee_location(item),
        tag_text,
    ]
    return "\n".join(field for field in fields if field) or None


def _recruitee_location(item: dict[str, Any]) -> str | None:
    locations = []
    raw_locations = item.get("locations")
    if isinstance(raw_locations, list):
        for entry in raw_locations:
            if not isinstance(entry, dict):
                continue
            name = _optional_str(entry.get("name"))
            city = _optional_str(entry.get("city"))
            country = _optional_str(entry.get("country"))
            note = _optional_str(entry.get("note"))
            location = ", ".join(part for part in (name or city, country, note) if part)
            if location:
                locations.append(location)
    fallback = _optional_str(item.get("location"))
    if fallback and fallback.lower() != "remote job":
        locations.append(fallback)
    return _bounded_text(", ".join(_dedupe_locations(locations)), 500) or None


def _pinpoint_description(item: dict[str, Any]) -> str:
    parts = [
        _optional_str(item.get("description")),
        _optional_str(item.get("key_responsibilities")),
        _optional_str(item.get("benefits")),
    ]
    return "\n\n".join(part for part in parts if part)


def _pinpoint_requirements(item: dict[str, Any]) -> str | None:
    job = item.get("job")
    department = None
    if isinstance(job, dict):
        raw_department = job.get("department")
        if isinstance(raw_department, dict):
            department = _optional_str(raw_department.get("name"))
    fields = [
        _optional_str(item.get("skills_knowledge_expertise")),
        _optional_str(item.get("employment_type_text")),
        _optional_str(item.get("workplace_type_text")),
        department,
    ]
    return "\n".join(field for field in fields if field) or None


def _pinpoint_location(item: dict[str, Any], location_hint: str | None = None) -> str | None:
    raw_location = item.get("location")
    locations: list[str] = []
    if isinstance(raw_location, dict):
        name = _optional_str(raw_location.get("name"))
        city = _optional_str(raw_location.get("city"))
        province = _optional_str(raw_location.get("province"))
        location_text = ", ".join(part for part in (city or name, province) if part)
        if location_text:
            locations.append(location_text)
    else:
        fallback_location = _optional_str(raw_location)
        if fallback_location:
            locations.append(fallback_location)
    if location_hint and not any(
        location_hint.lower() in location.lower() for location in locations if location
    ):
        locations.append(location_hint)
    location_text = ", ".join(_dedupe_locations(locations))
    return _bounded_text(location_text, 500) or None


def _pinpoint_salary_text(item: dict[str, Any]) -> str | None:
    compensation = _optional_str(item.get("compensation"))
    if compensation:
        return compensation
    minimum = item.get("compensation_minimum")
    maximum = item.get("compensation_maximum")
    currency = _optional_str(item.get("compensation_currency"))
    frequency = _optional_str(item.get("compensation_frequency"))
    if minimum is None and maximum is None:
        return None
    if minimum is None:
        salary_range = str(maximum)
    elif maximum is None or minimum == maximum:
        salary_range = str(minimum)
    else:
        salary_range = f"{minimum}-{maximum}"
    return " ".join(part for part in (salary_range, currency, frequency) if part)


def _personio_description(item: ET.Element) -> str:
    parts = []
    for description in item.findall("./jobDescriptions/jobDescription"):
        name = _personio_text(description, "name")
        value = _personio_text(description, "value")
        if value:
            parts.append(f"{name}: {value}" if name else value)
    return "\n\n".join(parts)


def _personio_requirements(item: ET.Element, years: str | None) -> str | None:
    fields = [
        _personio_text(item, "department"),
        _personio_text(item, "recruitingCategory"),
        _personio_text(item, "seniority"),
        _personio_text(item, "schedule"),
        _personio_text(item, "occupation"),
        _personio_text(item, "occupationCategory"),
        _personio_text(item, "keywords"),
        _personio_location(item),
    ]
    if years:
        fields.append(f"{years} years")
    return ", ".join(field for field in fields if field) or None


def _personio_location(item: ET.Element, location_hint: str | None = None) -> str | None:
    locations = [_personio_text(item, "office")]
    for office in item.findall("./additionalOffices/office"):
        if office.text:
            locations.append(_optional_str(office.text))
    if location_hint and not any(
        location_hint.lower() in location.lower() for location in locations if location
    ):
        locations.append(location_hint)
    location_text = ", ".join(_dedupe_locations([loc for loc in locations if loc]))
    return _bounded_text(location_text, 500) or None


def _personio_salary_text(item: ET.Element) -> str | None:
    salary = item.find("salaryInformation")
    if salary is None:
        return None
    minimum = _personio_text(salary, "min")
    maximum = _personio_text(salary, "max")
    currency = _personio_text(salary, "currencyCode") or _personio_text(
        salary, "currencySymbol"
    )
    salary_type = _personio_text(salary, "type")
    if not minimum and not maximum:
        return None
    if minimum and maximum and minimum != maximum:
        salary_range = f"{minimum}-{maximum}"
    else:
        salary_range = minimum or maximum or ""
    return " ".join(part for part in (salary_range, currency, salary_type) if part)


def _personio_url(item: ET.Element, company: CompanySetting, language: str) -> str | None:
    job_id = _personio_text(item, "id")
    if not job_id:
        return None
    base_url = f"https://{company.slug}.jobs.personio.de"
    return f"{base_url}/job/{job_id}?language={language}"


def _personio_payload(item: ET.Element) -> dict[str, Any]:
    return {child.tag: _personio_element_value(child) for child in list(item)}


def _personio_element_value(element: ET.Element) -> str | list[dict[str, str]]:
    children = list(element)
    if not children:
        return _optional_str(element.text) or ""
    return [
        {child.tag: _personio_element_text(child)}
        for child in children
        if _personio_element_text(child)
    ]


def _personio_element_text(element: ET.Element) -> str:
    return " ".join(" ".join(element.itertext()).split())


def _personio_text(item: ET.Element, path: str) -> str | None:
    element = item.find(path)
    if element is None:
        return None
    return _optional_str(_personio_element_text(element))


def _dedupe_locations(locations: list[str]) -> list[str]:
    deduped = []
    seen = set()
    for location in locations:
        key = location.lower()
        if key not in seen:
            seen.add(key)
            deduped.append(location)
    return deduped


def _location_name(value: object) -> str | None:
    if isinstance(value, dict):
        return _optional_str(value.get("name"))
    return _optional_str(value)


def _company_settings(value: object) -> list[CompanySetting]:
    if not isinstance(value, list):
        return []
    companies = []
    for item in value:
        if isinstance(item, str):
            companies.append(CompanySetting(slug=item, name=item.title()))
        elif isinstance(item, dict):
            slug = _optional_str(item.get("slug"))
            if slug:
                name = _optional_str(item.get("name")) or slug.title()
                location_hint = _optional_str(item.get("location_hint"))
                companies.append(
                    CompanySetting(slug=slug, name=name, location_hint=location_hint)
                )
    return companies


def _company_base_url(template: str | None, company: CompanySetting) -> str:
    base = template or "https://{company}"
    return base.format(company=company.slug, slug=company.slug)


def _string_list_from_dicts(value: list[object]) -> list[str]:
    items = []
    for entry in value:
        if isinstance(entry, dict):
            for key in ("name", "value"):
                text = _optional_str(entry.get(key))
                if text:
                    items.append(text)
    return items


def _country_from_location(location: str | None) -> str | None:
    if not location:
        return None
    lower = location.lower()
    if "worldwide" in lower or "global" in lower:
        return "Worldwide"
    if "spain" in lower or "madrid" in lower or "barcelona" in lower:
        return "Spain"
    if "europe" in lower or "emea" in lower or _looks_like_european_region(lower):
        return "Europe"
    return None


def _looks_like_european_region(location_lower: str) -> bool:
    european_terms = {
        "austria",
        "belgium",
        "bulgaria",
        "croatia",
        "cyprus",
        "czechia",
        "denmark",
        "estonia",
        "finland",
        "france",
        "germany",
        "greece",
        "hungary",
        "ireland",
        "italy",
        "latvia",
        "lithuania",
        "luxembourg",
        "netherlands",
        "poland",
        "portugal",
        "romania",
        "slovakia",
        "slovenia",
        "spain",
        "sweden",
    }
    return sum(term in location_lower for term in european_terms) >= 1


def _looks_remote(value: str | None) -> bool:
    if not value:
        return False
    lower = value.lower()
    return any(term in lower for term in ("remote", "worldwide", "global", "anywhere"))


def _parse_datetime(value: object) -> datetime | None:
    if not value:
        return None
    normalized = str(value).replace(" UTC", "+00:00").replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized).astimezone(UTC)
    except ValueError:
        return None


def _timestamp_ms_to_datetime(value: object) -> datetime | None:
    if not isinstance(value, (int, float, str, bytes)):
        return None
    try:
        return datetime.fromtimestamp(int(value) / 1000, tz=UTC)
    except (TypeError, ValueError, OSError):
        return None


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _bounded_text(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[: limit - 1].rstrip() + "..."


def _contains_keyword(text: str, keyword: str) -> bool:
    normalized = keyword.strip().lower()
    if not normalized:
        return False
    escaped = re.escape(normalized).replace(r"\ ", r"\s+")
    return re.search(rf"(?<!\w){escaped}(?!\w)", text, re.IGNORECASE) is not None
