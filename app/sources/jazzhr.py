"""Bounded public JazzHR boards; never read or submit applicant form values."""

from __future__ import annotations

import asyncio
import json
import re
from typing import Any
from urllib.parse import urljoin, urlsplit, urlunsplit

import httpx
from bs4 import BeautifulSoup

from app.models.enums import RemoteType
from app.scoring.text import clean_job_text
from app.sources.ats import GreenhouseJobSource, _filtered_jobs, _parse_datetime
from app.sources.base import RawJob, SearchConfig

TITLE = re.compile(r"java|spring|back[ -]?end|full[ -]?stack|software", re.IGNORECASE)
POSTING = re.compile(r"^/apply/([A-Za-z0-9]+)/[^/]+/?$")


class JazzHrJobSource(GreenhouseJobSource):
    name = "jazzhr_curated"

    def __init__(self, settings: dict[str, Any]) -> None:
        super().__init__({"base_url": "https://iriumspain.applytojob.com", **settings})
        self.min_interval_minutes = max(720, self.min_interval_minutes)
        self.rate_limit_seconds = max(1.0, self.rate_limit_seconds)
        self.retries = max(0, min(2, self.retries))
        self.max_details = max(1, min(10, int(settings.get("max_details_per_company", 10))))
        self.company_name = str(settings.get("company_name", "IRIUM - Spain"))
        self.location_hint = str(settings.get("location_hint", "")) or None
        self.country_hint = str(settings.get("country", "")) or None
        if not _public_board(str(self.base_url)):
            raise ValueError("JazzHR requires a configured HTTPS applytojob.com board")

    async def fetch_jobs(self, search_config: SearchConfig) -> list[RawJob]:
        jobs: list[RawJob] = []
        async with httpx.AsyncClient(
            timeout=self.timeout_seconds,
            headers={"User-Agent": "JobRadar/0.1 (personal public job research)"},
        ) as client:
            board = str(self.base_url).rstrip("/") + "/"
            html = await self._get_html(client, board)
            if not html:
                return []
            links: dict[str, str] = {}
            for anchor in BeautifulSoup(html, "html.parser").select("a[href]"):
                title = anchor.get_text(" ", strip=True)
                target = urljoin(board, str(anchor.get("href")))
                parsed = urlsplit(target)
                match = POSTING.fullmatch(parsed.path)
                if (
                    match
                    and TITLE.search(title)
                    and _same_board(target, board)
                    and match[1] not in links
                ):
                    links[match[1]] = urlunsplit(("https", parsed.netloc, parsed.path, "", ""))
            for identity, url in list(links.items())[: self.max_details]:
                detail = await self._get_html(client, url)
                if not detail:
                    continue
                job = self._to_job(detail, url, identity)
                if job:
                    jobs.append(job)
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

    async def _get_html(self, client: httpx.AsyncClient, url: str) -> str | None:
        for attempt in range(self.retries + 1):
            try:
                target = url
                for _ in range(3):
                    await asyncio.sleep(self.rate_limit_seconds)
                    response = await client.get(target, follow_redirects=False)
                    if not response.is_redirect:
                        break
                    target = urljoin(target, response.headers.get("location", ""))
                    if not _same_board(target, str(self.base_url)) or not (
                        urlsplit(target).path in {"", "/", "/apply", "/apply/"}
                        or POSTING.fullmatch(urlsplit(target).path)
                    ):
                        return None
                else:
                    return None
                if response.status_code in {403, 404, 410, 429}:
                    return None
                response.raise_for_status()
                return response.text
            except httpx.HTTPError:
                if attempt == self.retries:
                    raise
        return None

    def _to_job(self, html: str, url: str, identity: str) -> RawJob | None:
        soup = BeautifulSoup(html, "html.parser")
        posting = _job_posting(soup)
        for private in soup.select(
            "form, input, textarea, select, script, style, nav, footer, "
            "#job-application-form-container, .job-application-form"
        ):
            private.decompose()
        heading = soup.select_one(".job-header h2, .job-title, #job-title")
        if heading is None:
            heading = soup.select_one("h1:not(.brand-text)") or soup.select_one("h2")
        title = str(posting.get("title") or (heading.get_text(" ", strip=True) if heading else ""))
        description_node = soup.select_one("#job-description, .job-description, .description")
        description_html = str(posting.get("description") or description_node or "")
        if not title or not description_html:
            return None
        safe_description = BeautifulSoup(description_html, "html.parser")
        for private in safe_description.select("form, input, textarea, select, script, style"):
            private.decompose()
        description = clean_job_text(str(safe_description))
        if re.search(
            r"no longer accepting applications|position (?:is )?closed", description, re.I
        ):
            return None
        location, country = _location(posting)
        location = location or self.location_hint
        country = country or self.country_hint
        if not country and re.search(r"\b(?:españa|spain)\b", f"{location} {description}", re.I):
            country = "Spain"
        remote = str(posting.get("jobLocationType", "")).upper() == "TELECOMMUTE"
        if not remote:
            remote = bool(
                re.search(r"100\s*%\s*(?:remoto|teletrabajo)|fully remote", description, re.I)
            )
        salary_match = re.search(
            r"(?:salario|salary|banda salarial)[^\n]{0,100}", description, re.IGNORECASE
        )
        payload = {
            "title": title,
            "description": description,
            "location": location,
            "country": country,
            "datePosted": posting.get("datePosted"),
            "validThrough": posting.get("validThrough"),
            "jobLocationType": posting.get("jobLocationType"),
            "url": url,
        }
        return RawJob(
            source_name=self.name,
            source_job_id=f"{urlsplit(url).hostname}:{identity}",
            company_name=self.company_name,
            title=title,
            description=description,
            location=location,
            country=country,
            remote_type=RemoteType.REMOTE if remote else RemoteType.UNKNOWN,
            employment_type=(
                str(posting["employmentType"]) if posting.get("employmentType") else None
            ),
            salary_original_text=salary_match[0] if salary_match else None,
            url=url,
            publication_date=_parse_datetime(posting.get("datePosted")),
            expiration_date=_parse_datetime(posting.get("validThrough")),
            raw_payload=payload,
        )


def _public_board(url: str) -> bool:
    try:
        parsed = urlsplit(url)
        return (
            parsed.scheme == "https"
            and (parsed.hostname or "").endswith(".applytojob.com")
            and not parsed.username
            and not parsed.password
            and parsed.port in {None, 443}
        )
    except ValueError:
        return False


def _same_board(url: str, board: str) -> bool:
    return _public_board(url) and urlsplit(url).hostname == urlsplit(board).hostname


def _job_posting(soup: BeautifulSoup) -> dict[str, Any]:
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            value = json.loads(script.get_text())
        except (ValueError, TypeError):
            continue
        candidates = value if isinstance(value, list) else [value]
        for item in candidates:
            if isinstance(item, dict) and isinstance(item.get("@graph"), list):
                candidates.extend(item["@graph"])
            if isinstance(item, dict) and item.get("@type") == "JobPosting":
                return item
    return {}


def _location(posting: dict[str, Any]) -> tuple[str | None, str | None]:
    place = posting.get("jobLocation", {})
    if isinstance(place, list):
        place = place[0] if place else {}
    address = place.get("address", {}) if isinstance(place, dict) else {}
    address = address if isinstance(address, dict) else {}
    location = str(address.get("addressLocality") or address.get("addressRegion") or "") or None
    country = address.get("addressCountry")
    applicant = posting.get("applicantLocationRequirements", {})
    if isinstance(applicant, dict):
        country = country or applicant.get("name")
    if isinstance(country, dict):
        country = country.get("name")
    country = str(country) if country else None
    if country and country.lower() in {"es", "espana", "españa", "spain"}:
        country = "Spain"
    return location, country
