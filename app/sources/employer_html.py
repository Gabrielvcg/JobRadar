"""Bounded public employer indexes with JobPosting and visible job content."""

from __future__ import annotations

import asyncio
import json
import re
from typing import Any
from urllib.parse import urljoin, urlsplit

import httpx
from bs4 import BeautifulSoup

from app.models.enums import RemoteType
from app.sources.ats import _matches_affinity
from app.sources.base import RawJob, SearchConfig
from app.sources.bizneo import _contains_keyword


class EmployerHtmlJobSource:
    name = "employer_html"

    def __init__(self, settings: dict[str, Any]) -> None:
        self.enabled = bool(settings.get("enabled", True))
        self.base_url: str | None = str(settings["base_url"])
        self.company_name = str(settings["company_name"])
        self.index_urls = [str(url) for url in settings.get("index_urls", [])]
        self.link_selector = str(settings["link_selector"])
        self.description_selector = str(settings["description_selector"])
        self.location_selector = str(settings["location_selector"])
        self.mode_selector = str(settings["mode_selector"])
        self.min_interval_minutes = int(settings.get("min_interval_minutes", 720))
        self.minimum_score = int(settings.get("minimum_score", 35))
        self.timeout_seconds = float(settings.get("timeout_seconds", 20))
        self.rate_limit_seconds = float(settings.get("rate_limit_seconds", 1))
        self.max_detail_pages = int(settings.get("max_detail_pages", 10))
        self.title_required_any_keywords = list(settings.get("title_required_any_keywords", []))
        self.required_any_keywords = list(settings.get("required_any_keywords", []))

    def _links(self, payload: str, index: str) -> list[str]:
        soup = BeautifulSoup(payload, "html.parser")
        links = []
        for element in soup.select(self.link_selector):
            title = element.get_text(" ", strip=True)
            if self.title_required_any_keywords and not any(
                _contains_keyword(title, word) for word in self.title_required_any_keywords
            ):
                continue
            url = urljoin(index, str(element.get("href", "")))
            if self._same_origin(url):
                links.append(url)
        return list(dict.fromkeys(links))

    def _same_origin(self, url: str) -> bool:
        parsed, base = urlsplit(url), urlsplit(str(self.base_url))
        return (
            parsed.scheme == "https"
            and parsed.netloc == base.netloc
            and not parsed.username
            and not parsed.password
        )

    def _parse(self, payload: str, url: str) -> RawJob | None:
        soup = BeautifulSoup(payload, "html.parser")
        posting = None
        for script in soup.select('script[type="application/ld+json"]'):
            try:
                # Some public pages contain unescaped literal newlines in strings.
                item = json.loads(script.get_text(), strict=False)
            except ValueError:
                continue
            items = item if isinstance(item, list) else [item]
            posting = next(
                (
                    value
                    for value in items
                    if isinstance(value, dict) and value.get("@type") == "JobPosting"
                ),
                None,
            )
            if posting:
                break
        heading = soup.select_one("h1")
        blocks = soup.select(self.description_selector)
        location = soup.select_one(self.location_selector)
        mode = soup.select_one(self.mode_selector)
        if not posting or heading is None or not blocks or location is None:
            return None
        title = heading.get_text(" ", strip=True)
        declared = str(posting.get("title") or posting.get("name") or "")
        if not declared or not title or title.casefold() not in declared.casefold():
            return None
        # JSON-LD may contain only company benefits. Retain actual visible duties,
        # requirements and list boundaries, without newsletter/application widgets.
        description = "\n".join(str(block) for block in blocks)
        mode_text = mode.get_text(" ", strip=True) if mode else ""
        remote = (
            RemoteType.REMOTE
            if re.search(r"(?:remot\w*|teletrabajo).*100\s*%", mode_text, re.I)
            else RemoteType.UNKNOWN
        )
        return RawJob(
            source_name=self.name,
            source_job_id=urlsplit(url).path.rstrip("/"),
            company_name=self.company_name,
            company_website=self.base_url,
            title=title,
            description=description,
            location=location.get_text(" ", strip=True),
            remote_type=remote,
            url=url,
            raw_payload={
                "index_urls": self.index_urls,
                "url": url,
                "metadata_title": declared,
                "work_mode": mode_text,
            },
        )

    async def fetch_jobs(self, search_config: SearchConfig) -> list[RawJob]:
        links: list[str] = []
        jobs: list[RawJob] = []
        async with httpx.AsyncClient(
            timeout=self.timeout_seconds,
            headers={"User-Agent": "JobRadar/0.1 (personal job research; attribution retained)"},
        ) as client:
            for index in self.index_urls:
                if not self._same_origin(index):
                    continue
                response = await client.get(index, follow_redirects=False)
                response.raise_for_status()
                links.extend(self._links(response.text, index))
                await asyncio.sleep(self.rate_limit_seconds)
            for url in list(dict.fromkeys(links))[: self.max_detail_pages]:
                response = await client.get(url, follow_redirects=False)
                if response.status_code in {404, 410}:
                    continue
                response.raise_for_status()
                job = self._parse(response.text, url)
                if job:
                    jobs.append(job)
                await asyncio.sleep(self.rate_limit_seconds)
        return [
            job
            for job in jobs
            if _matches_affinity(
                job,
                search_config.queries,
                self.required_any_keywords,
                self.title_required_any_keywords,
                [],
                [],
            )
        ]
