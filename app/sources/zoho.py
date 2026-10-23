"""Public Zoho career RSS with complete server-rendered vacancy fields."""

from __future__ import annotations

import asyncio
import json
import re
from dataclasses import replace
from typing import Any
from urllib.parse import urlsplit

import httpx

from app.models.enums import RemoteType
from app.scoring.text import clean_job_text
from app.sources.base import RawJob, SearchConfig
from app.sources.rss import RssJobSource, _matches_affinity

JOBS = re.compile(r"\bvar jobs\s*=\s*JSON\.parse\('((?:\\.|[^'\\])*)'\)")
ESCAPE = re.compile(r"\\(x[0-9a-fA-F]{2}|u[0-9a-fA-F]{4}|[\s\S])")


def _unescape(match: re.Match[str]) -> str:
    value = match[1]
    if value.startswith(("x", "u")) and len(value) > 1:
        return chr(int(value[1:], 16))
    return {"n": "\n", "r": "\r", "t": "\t", "b": "\b", "f": "\f"}.get(value, value)


def public_job(payload: str, job_id: str) -> dict[str, Any]:
    """Decode JSON data only; never evaluate employer JavaScript."""
    match = JOBS.search(payload)
    if not match:
        raise ValueError("Zoho vacancy has no public job data")
    values = json.loads(ESCAPE.sub(_unescape, match[1]))
    if not isinstance(values, list) or len(values) != 1:
        raise ValueError("Zoho detail must identify exactly one vacancy")
    job = values[0]
    if not isinstance(job, dict) or str(job.get("id")) != job_id:
        raise ValueError("Zoho detail does not match the RSS vacancy identity")
    return job


class ZohoRssJobSource(RssJobSource):
    def __init__(self, name: str, settings: dict[str, Any]) -> None:
        super().__init__(name, settings)
        self.description_fields = list(settings.get("description_fields", ["Job_Description"]))
        self.requirement_fields = list(settings.get("requirement_fields", []))
        self.max_detail_pages = int(settings.get("max_detail_pages", 5))
        self.rate_limit_seconds = float(settings.get("rate_limit_seconds", 1))

    def _job_id(self, url: str | None) -> str:
        target, base = urlsplit(url or ""), urlsplit(str(self.base_url))
        if (
            target.scheme != "https"
            or target.netloc != base.netloc
            or target.username
            or target.password
            or not (target.hostname or "").endswith(".zohorecruit.com")
        ):
            raise ValueError("Zoho detail must remain on its configured public employer host")
        match = re.search(r"/jobs/[^/]+/(\d+)(?:/|$)", target.path)
        if not match:
            raise ValueError("Zoho vacancy URL has no public job identity")
        return match[1]

    def _enrich(self, raw: RawJob, payload: str) -> RawJob:
        job = public_job(payload, self._job_id(raw.url))
        title = str(job.get("Posting_Title") or "")
        if clean_job_text(title).casefold() != clean_job_text(raw.title).casefold():
            raise ValueError("Zoho detail title does not match the RSS vacancy")
        description = "\n".join(str(job.get(key) or "") for key in self.description_fields)
        requirements = "\n".join(str(job.get(key) or "") for key in self.requirement_fields)
        # Retain conflicting structured experience rather than choosing the easier number.
        years = str(job.get("Work_Experience") or "")
        if years:
            requirements += f"\nWork experience (structured): {years}"
        country = str(job.get("Country") or "")
        location = ", ".join(str(job.get(key) or "") for key in ("City", "State", "Country"))
        return replace(
            raw,
            source_job_id=str(job["id"]),
            description=description,
            requirements=requirements or None,
            location=location,
            country=country or None,
            # RSS's generic remote default is insufficient evidence for a Zoho job.
            remote_type=RemoteType.UNKNOWN,
            employment_type=str(job.get("Job_Type") or "") or None,
            raw_payload={**raw.raw_payload, "public_job": job},
        )

    async def fetch_jobs(self, search_config: SearchConfig) -> list[RawJob]:
        candidates = await super().fetch_jobs(search_config)
        jobs = []
        async with httpx.AsyncClient(
            timeout=self.timeout_seconds,
            headers={"User-Agent": "JobRadar/0.1 (personal job research; attribution retained)"},
        ) as client:
            for raw in candidates[: self.max_detail_pages]:
                self._job_id(raw.url)
                response = await client.get(str(raw.url), follow_redirects=False)
                if response.status_code in {404, 410}:
                    continue
                response.raise_for_status()
                job = self._enrich(raw, response.text)
                if _matches_affinity(
                    job,
                    search_config.queries,
                    self.required_any_keywords,
                    self.title_required_any_keywords,
                    self.excluded_keywords,
                    self.allowed_location_keywords,
                    self.must_have_any_keywords,
                    self.allow_career_transitions,
                ):
                    jobs.append(job)
                await asyncio.sleep(self.rate_limit_seconds)
        return jobs
