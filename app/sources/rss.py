from __future__ import annotations

import asyncio
import logging
import re
import xml.etree.ElementTree as ET
from dataclasses import replace
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any

import httpx

from app.core.career_paths import matches_career_transition
from app.core.config import get_settings
from app.models.enums import RemoteType
from app.scoring.text import clean_job_text, normalize_whitespace
from app.sources.base import RawJob, SearchConfig

logger = logging.getLogger(__name__)


class RssJobSource:
    def __init__(self, name: str, settings: dict[str, Any]) -> None:
        self.name = name
        self.enabled = bool(settings.get("enabled", True))
        self.base_url: str | None = str(settings.get("base_url", ""))
        self.timeout_seconds = float(
            settings.get("timeout_seconds", get_settings().http_timeout_seconds)
        )
        self.retries = int(settings.get("retries", 2))
        self.min_interval_minutes = int(settings.get("min_interval_minutes", 360))
        self.minimum_score = int(settings.get("minimum_score", 35))
        self.allow_career_transitions = bool(settings.get("allow_career_transitions", False))
        self.must_have_any_keywords = _string_list(settings.get("must_have_any_keywords", []))
        self.required_any_keywords = _string_list(settings.get("required_any_keywords", []))
        self.title_required_any_keywords = _string_list(
            settings.get("title_required_any_keywords", [])
        )
        self.excluded_keywords = _string_list(settings.get("excluded_keywords", []))
        self.allowed_location_keywords = _string_list(settings.get("allowed_location_keywords", []))
        self.max_jobs = int(settings.get("max_jobs", 50))
        self.company_name = str(settings.get("company_name") or "")

    async def fetch_jobs(self, search_config: SearchConfig) -> list[RawJob]:
        payload = await self._fetch_payload()
        jobs = [self._to_raw_job(item) for item in _rss_items(payload)]
        filtered = [
            job
            for job in jobs[: self.max_jobs]
            if _matches_affinity(
                job,
                search_config.queries,
                self.required_any_keywords,
                self.title_required_any_keywords,
                self.excluded_keywords,
                self.allowed_location_keywords,
                self.must_have_any_keywords,
                self.allow_career_transitions,
            )
        ]
        return _exact_variants(filtered) if self.company_name else filtered

    async def _fetch_payload(self) -> str:
        headers = {
            "Accept": "application/rss+xml, application/xml, text/xml",
            "User-Agent": "JobRadar/0.1 (personal job research; source attribution kept)",
        }
        last_error: Exception | None = None
        async with httpx.AsyncClient(
            timeout=self.timeout_seconds, headers=headers, follow_redirects=True
        ) as client:
            for attempt in range(self.retries + 1):
                try:
                    response = await client.get(str(self.base_url))
                    response.raise_for_status()
                    return response.text
                except httpx.HTTPError as exc:
                    last_error = exc
                    wait_seconds = min(2**attempt, 8)
                    logger.warning(
                        "Fallo temporal consultando fuente RSS",
                        extra={"source": self.name, "attempt": attempt + 1},
                    )
                    await asyncio.sleep(wait_seconds)
        raise RuntimeError(f"RSS source {self.name} failed after retries: {last_error}")

    def _to_raw_job(self, item: ET.Element) -> RawJob:
        raw_title = _child_text(item, "title") or "Untitled job"
        company_name, title = _split_company_title(raw_title)
        if self.company_name:
            company_name, title = self.company_name, raw_title
        region = _child_text(item, "region")
        country = _child_text(item, "country")
        state = _child_text(item, "state")
        skills = _child_text(item, "skills")
        category = _child_text(item, "category")
        description = _child_text(item, "description") or ""
        requirements = ", ".join(part for part in (category, skills, region, country) if part)
        location = ", ".join(part for part in (region, country or state) if part)
        remote_type = RemoteType.REMOTE
        # Teamtailor publishes these fields in its documented public RSS feed.
        ns = "{https://teamtailor.com/locations}"
        places = item.findall(f"{ns}locations/{ns}location")
        if places:
            cities = list(
                dict.fromkeys(
                    p.findtext(f"{ns}city") or p.findtext(f"{ns}name") or "" for p in places
                )
            )
            countries = list(dict.fromkeys(p.findtext(f"{ns}country") or "" for p in places))
            location = ", ".join(p for p in [*cities, *countries] if p)[:500]
            country = countries[0] if len(countries) == 1 else None
        status = _child_text(item, "remoteStatus")
        if status:
            remote_type = {
                "fully": RemoteType.REMOTE,
                "hybrid": RemoteType.HYBRID,
                "none": RemoteType.ONSITE,
            }.get(status, RemoteType.UNKNOWN)
        return RawJob(
            source_name=self.name,
            source_job_id=_child_text(item, "guid") or _child_text(item, "link"),
            company_name=company_name,
            title=title,
            description=description,
            requirements=requirements or None,
            location=location or region,
            country=(country or _country_from_location(location))
            if places
            else _country_from_location(location or region),
            remote_type=remote_type,
            employment_type=None,
            url=_child_text(item, "link"),
            publication_date=_parse_rss_datetime(_child_text(item, "pubDate")),
            raw_payload={
                "description": description,
                "title": raw_title,
                "region": region,
                "category": category,
                "country": country,
                "skills": skills,
            },
        )


def _rss_items(payload: str) -> list[ET.Element]:
    root = ET.fromstring(payload)
    return list(root.findall("./channel/item"))


def _exact_variants(jobs: list[RawJob]) -> list[RawJob]:
    groups: dict[tuple[str, ...], RawJob] = {}
    for job in jobs:
        place = (
            job.country if job.remote_type == RemoteType.REMOTE and job.country else job.location
        )
        key = (
            job.company_name.casefold(),
            job.title.casefold(),
            (place or "").casefold(),
            job.remote_type.value,
            normalize_whitespace(clean_job_text(job.description)).casefold(),
            job.requirements or "",
        )
        previous = groups.get(key)
        variants = list(previous.raw_payload.get("alternate_postings", [])) if previous else []
        variants.append(
            {
                "source_job_id": job.source_job_id,
                "url": job.url,
                "location": job.location,
            }
        )
        chosen = previous or job
        groups[key] = replace(
            chosen, raw_payload={**chosen.raw_payload, "alternate_postings": variants}
        )
    return list(groups.values())


def _matches_affinity(
    job: RawJob,
    queries: list[str],
    required_any_keywords: list[str],
    title_required_any_keywords: list[str],
    excluded_keywords: list[str],
    allowed_location_keywords: list[str],
    must_have_any_keywords: list[str] | None = None,
    allow_career_transitions: bool = False,
) -> bool:
    title = job.title.lower()
    location = (job.location or "").lower()
    haystack = f"{job.title} {job.description} {job.requirements or ''}".lower()
    if (
        allowed_location_keywords
        and location
        and not any(keyword.lower() in location for keyword in allowed_location_keywords)
    ):
        return False
    if (
        must_have_any_keywords
        and not any(_contains_keyword(haystack, keyword) for keyword in must_have_any_keywords)
        and not (allow_career_transitions and matches_career_transition(job.title, haystack))
    ):
        return False
    if any(_contains_keyword(haystack, keyword) for keyword in excluded_keywords):
        return False
    if title_required_any_keywords and not any(
        _contains_keyword(title, keyword) for keyword in title_required_any_keywords
    ):
        return False
    if required_any_keywords:
        return any(_contains_keyword(haystack, keyword) for keyword in required_any_keywords)
    return any(_contains_keyword(haystack, query) for query in queries)


def _child_text(item: ET.Element, name: str) -> str | None:
    child = item.find(name)
    if child is None or child.text is None:
        return None
    text = child.text.strip()
    return text or None


def _split_company_title(raw_title: str) -> tuple[str, str]:
    if ":" not in raw_title:
        return "Unknown company", raw_title.strip()
    company, title = raw_title.split(":", 1)
    return company.strip() or "Unknown company", title.strip() or raw_title.strip()


def _parse_rss_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _country_from_location(location: str | None) -> str | None:
    if not location:
        return None
    location_lower = location.lower()
    if "europe" in location_lower:
        return "Europe"
    if "spain" in location_lower:
        return "Spain"
    if "world" in location_lower or "anywhere" in location_lower:
        return location
    return None


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _contains_keyword(text: str, keyword: str) -> bool:
    normalized = keyword.strip().lower()
    if not normalized:
        return False
    escaped = re.escape(normalized).replace(r"\ ", r"\s+")
    return re.search(rf"(?<!\w){escaped}(?!\w)", text, re.IGNORECASE) is not None
