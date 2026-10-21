"""Bounded reads of the official public Posting API for curated employers."""

from __future__ import annotations

import asyncio
from typing import Any
from urllib.parse import quote

import httpx

from app.models.enums import RemoteType
from app.sources.ats import GreenhouseJobSource, _filtered_jobs, _parse_datetime
from app.sources.base import RawJob, SearchConfig


class SmartRecruitersJobSource(GreenhouseJobSource):
    name = "smartrecruiters_curated"

    def __init__(self, settings: dict[str, Any]) -> None:
        super().__init__({"base_url": "https://api.smartrecruiters.com", **settings})
        self.query = str(settings.get("query", "Java"))
        self.country = str(settings.get("country", "es"))
        self.max_pages = max(1, min(5, int(settings.get("max_pages", 1))))
        self.page_size = max(1, min(100, int(settings.get("page_size", 50))))
        self.max_details = max(1, min(100, int(settings.get("max_details_per_company", 20))))

    async def fetch_jobs(self, search_config: SearchConfig) -> list[RawJob]:
        jobs: list[RawJob] = []
        async with httpx.AsyncClient(
            timeout=self.timeout_seconds,
            headers={
                "Accept": "application/json",
                "User-Agent": "JobRadar/0.1 (personal job research)",
            },
        ) as client:
            for company in self.companies:
                base = f"{self.base_url}/v1/companies/{quote(company.slug, safe='')}/postings"
                seen: set[str] = set()
                for page in range(self.max_pages):
                    listing = await self._get_json(
                        client,
                        base,
                        {
                            "q": self.query,
                            "country": self.country,
                            "limit": self.page_size,
                            "offset": page * self.page_size,
                        },
                    )
                    items = listing.get("content", [])
                    if not isinstance(items, list):
                        raise ValueError("SmartRecruiters content must be a list")
                    for item in items:
                        if not isinstance(item, dict) or not item.get("id"):
                            continue
                        identity = str(item["id"])
                        if identity in seen or len(seen) >= self.max_details:
                            continue
                        if item.get("visibility", "PUBLIC") != "PUBLIC":
                            continue
                        seen.add(identity)
                        details = await self._get_json(client, f"{base}/{quote(identity, safe='')}")
                        if (
                            details.get("active", True)
                            and details.get("visibility", "PUBLIC") == "PUBLIC"
                        ):
                            jobs.append(self._to_job(details, company.slug, company.name))
                    if len(items) < self.page_size or len(seen) >= self.max_details:
                        break
        return _filtered_jobs(
            jobs,
            search_config,
            self.required_any_keywords,
            self.title_required_any_keywords,
            self.excluded_keywords,
            self.allowed_location_keywords,
            self.must_have_any_keywords,
            self.allow_career_transitions,
        )

    async def _get_json(
        self,
        client: httpx.AsyncClient,
        url: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        for attempt in range(self.retries + 1):
            await asyncio.sleep(self.rate_limit_seconds)
            response = await client.get(url, params=params)
            if (
                response.status_code == 429 or response.status_code >= 500
            ) and attempt < self.retries:
                await asyncio.sleep(min(2**attempt, 8))
                continue
            response.raise_for_status()
            result = response.json()
            if not isinstance(result, dict):
                raise ValueError("SmartRecruiters must return a JSON object")
            return result
        raise RuntimeError("SmartRecruiters exhausted retries")

    def _to_job(self, item: dict[str, Any], company_slug: str, company_name: str) -> RawJob:
        location = item.get("location") or {}
        sections = (item.get("jobAd") or {}).get("sections") or {}
        description = "\n".join(
            str((sections.get(key) or {}).get("text") or "")
            for key in (
                "jobDescription",
                "additionalInformation",
            )
        )
        requirements = str((sections.get("qualifications") or {}).get("text") or "")
        country = str(location.get("country") or "")
        country = "Spain" if country.lower() == "es" else country
        place = ", ".join(str(x) for x in (location.get("city"), country) if x)
        mode = (
            RemoteType.HYBRID
            if location.get("hybrid")
            else (RemoteType.REMOTE if location.get("remote") else RemoteType.UNKNOWN)
        )
        # Keep job evidence, excluding creator/contact metadata from the public response.
        payload: dict[str, Any] = {
            key: item[key] for key in ("id", "name", "jobAd", "location", "active") if key in item
        }
        return RawJob(
            source_name=self.name,
            source_job_id=f"{company_slug}:{item['id']}",
            company_name=company_name,
            title=str(item.get("name") or "Untitled job"),
            description=description,
            requirements=requirements or None,
            location=place,
            country=country or None,
            remote_type=mode,
            employment_type=str((item.get("typeOfEmployment") or {}).get("label") or "") or None,
            url=str(
                item.get("applyUrl")
                or f"https://jobs.smartrecruiters.com/{company_slug}/{item['id']}"
            ),
            publication_date=_parse_datetime(item.get("releasedDate")),
            raw_payload=payload,
        )
