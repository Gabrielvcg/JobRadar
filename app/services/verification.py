"""Conservative public-page checks. Never submit applications or bypass access controls."""

from __future__ import annotations

import asyncio
import re
from collections.abc import Generator
from datetime import UTC, datetime
from heapq import nsmallest
from typing import Any
from urllib.parse import parse_qs, urljoin, urlsplit

import httpx
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session

from app.core.availability import VERIFICATION_KEY, current_verification
from app.core.offer_identity import EMPLOYER_SUFFIXES, TEAMTAILOR_HOSTS
from app.core.profiles import load_profiles, uses_career_radar
from app.models.job import JobOffer
from app.repositories.jobs import JobFilters, JobRepository
from app.scoring.engine import ScoringEngine
from app.scoring.evidence import fold
from app.scoring.text import canonical_url

PUBLIC_HOSTS = {
    "jobs.experienceis.com",
    "www.sngular.com",
    "himalayas.app",
    "remotive.com",
    "remoteok.com",
    "weworkremotely.com",
    "jobicy.com",
    "www.arbeitnow.com",
    "www.tecnoempleo.com",
    "www.pagepersonnel.es",
    "www.portalento.es",
    "empleo.fundacionadecco.org",
    "jobs.smartrecruiters.com",
    "careers.smartrecruiters.com",
    "jobs.lever.co",
    "jobs.eu.lever.co",
    "boards.greenhouse.io",
    "job-boards.greenhouse.io",
    "apply.workable.com",
    "jobs.ashbyhq.com",
} | TEAMTAILOR_HOSTS
ATS_SUFFIXES = EMPLOYER_SUFFIXES
CLOSED = re.compile(
    r"\b(?:this (?:job|position|vacancy) (?:is no longer available|has been filled|is closed)|"
    r"no longer accepting applications|job (?:has )?expired|position filled|"
    r"oferta (?:caducada|finalizada|cerrada)|vacante (?:cerrada|cubierta)|"
    r"ya no (?:acepta|se aceptan) (?:solicitudes|candidaturas))\b"
)
APPLY = re.compile(
    r"^(?:apply(?: now| for (?:this|the) (?:job|position)| on company site)?|"
    r"me interesa|i.m interested|solicitar(?: este puesto)?|inscrib\w*|postular\w*|"
    r"enviar cv|enviar solicitud|submit application|solicitar este empleo|"
    r"apply for this job|inscrib\w* ahora)$"
)


def supported_url(url: str | None) -> bool:
    if not url:
        return False
    try:
        parsed = urlsplit(url)
        port = parsed.port
    except ValueError:
        return False
    host = (parsed.hostname or "").lower()
    return (
        parsed.scheme == "https"
        and not parsed.username
        and not parsed.password
        and (host in PUBLIC_HOSTS or host.endswith(ATS_SUFFIXES))
        and port in {None, 443}
    )


async def verify_listing(
    client: httpx.AsyncClient,
    url: str | None,
    title: str | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "state": "unverified",
        "listing_url": canonical_url(url),
        "checked_at": datetime.now(UTC).isoformat(),
        "application_url": None,
        "reason": "Listing host is not supported for automatic verification",
    }
    if not supported_url(url):
        return result
    target = str(url)
    try:
        for _ in range(4):
            response = await client.get(target, follow_redirects=False)
            if response.is_redirect:
                target = urljoin(target, response.headers.get("location", ""))
                if not supported_url(target):
                    result["reason"] = "Redirect requires manual verification on the employer site"
                    return result
                continue
            break
        else:
            result["reason"] = "Too many redirects; manual verification required"
            return result
        result["http_status"] = response.status_code
        if response.status_code in {404, 410}:
            return {**result, "state": "closed", "reason": "Listing was removed (HTTP 404/410)"}
        if response.status_code != 200:
            result["reason"] = (
                "Access blocked or unavailable; this does not prove the vacancy closed"
            )
            return result
        soup = BeautifulSoup(response.text, "html.parser")
        text = fold(soup.get_text(" ", strip=True))
        if CLOSED.search(text):
            return {
                **result,
                "state": "closed",
                "reason": "Listing explicitly says applications closed",
            }
        if title:
            expected = set(re.findall(r"\w+", fold(title)))
            headings = [h for h in soup.select("h1, title") if h.get_text(strip=True)]
            matches = any(
                len(expected & set(re.findall(r"\w+", fold(h.get_text(" ")))))
                / max(1, len(expected))
                >= 0.6
                for h in headings
            )
            if not expected or not matches:
                greenhouse = re.fullmatch(r"/([\w-]+)/jobs/(\d+)", urlsplit(str(url)).path)
                if greenhouse and urlsplit(str(url)).hostname in {
                    "boards.greenhouse.io",
                    "job-boards.greenhouse.io",
                }:
                    endpoint = (
                        f"https://boards-api.greenhouse.io/v1/boards/{greenhouse[1]}"
                        f"/jobs/{greenhouse[2]}"
                    )
                    official = await client.get(endpoint, follow_redirects=False)
                    if official.status_code == 404:
                        return {
                            **result,
                            "state": "closed",
                            "reason": "Official posting API confirms removal",
                            "evidence_url": endpoint,
                            "evidence_http_status": 404,
                        }
                result["reason"] = "Page does not confirm the expected vacancy title"
                return result
        if urlsplit(target).hostname == "jobs.experienceis.com":
            controller = soup.select_one("#job-inscription[hx-get]")
            if controller:
                destination = urljoin(target, str(controller.get("hx-get")))
                parsed, listing = urlsplit(destination), urlsplit(target)
                job_id = listing.path.rstrip("/").rsplit("/", 1)[-1]
                if (
                    supported_url(destination)
                    and parsed.netloc == listing.netloc
                    and parsed.path == "/registration/new"
                    and parse_qs(parsed.query) == {"job_id": [job_id]}
                ):
                    form_page = await client.get(destination, follow_redirects=False)
                    if form_page.status_code == 200 and _bizneo_form(form_page.text, destination):
                        return {
                            **result,
                            "state": "active",
                            "application_url": destination,
                            "evidence_level": "application_form",
                            "reason": "Vacancy-specific candidate and CV upload form accessible",
                        }
        if urlsplit(target).hostname == "www.sngular.com":
            form = soup.select_one('form[action="/es/talent-form"]')
            bound_title = form.select_one('input[name="talent[title]"]') if form else None
            heading = soup.select_one("h1")
            if (
                form is not None
                and bound_title is not None
                and heading is not None
                and fold(str(bound_title.get("value"))) == fold(heading.get_text(" ", strip=True))
                and _candidate_form(str(form))
                and form.select_one('button[type="submit"][data-talent-target="btnSubmit"]')
                is not None
            ):
                return {
                    **result,
                    "state": "active",
                    "application_url": target + "#talent",
                    "evidence_level": "application_form",
                    "reason": (
                        "Vacancy-bound CV form accessible; "
                        "applicant must complete consent and CAPTCHA"
                    ),
                }
        teamtailor = (urlsplit(target).hostname or "").endswith(".teamtailor.com") or (
            urlsplit(target).hostname in TEAMTAILOR_HOSTS
        )
        if teamtailor:
            # Teamtailor explicitly binds its public form URL to the page controller.
            # Floating buttons are disabled templates until JavaScript initializes.
            attribute = "data-careersite--jobs--form-overlay-job-application-url-value"
            controller = soup.select_one(f"[{attribute}]")
            if controller:
                destination = urljoin(target, str(controller.get(attribute)))
                parsed = urlsplit(destination)
                listing = urlsplit(target)
                if (
                    supported_url(destination)
                    and parsed.netloc == listing.netloc
                    and parsed.path == listing.path.rstrip("/") + "/applications/new"
                    and not parsed.query
                ):
                    form_page = await client.get(destination, follow_redirects=False)
                    if form_page.status_code == 200 and _teamtailor_form(
                        form_page.text, destination
                    ):
                        return {
                            **result,
                            "state": "active",
                            "application_url": destination,
                            "evidence_level": "application_form",
                            "reason": "Public vacancy links to an accessible candidate upload form",
                        }
        controls = list(soup.select("a[href], button, input[type=submit]"))
        # SmartRecruiters binds its observed public application links with JavaScript.
        # Keep the user on the verified listing rather than guessing a form URL.
        if urlsplit(target).hostname == "jobs.smartrecruiters.com":
            controls.extend(soup.select('a.js-oneclick[data-sr-track="apply"]'))
        checked_forms: dict[str, bool] = {}
        for element in controls:
            label = fold(element.get_text(" ", strip=True) or str(element.get("value") or ""))
            label = label.strip(" \t›→!…")
            if (
                not APPLY.search(label)
                or element.has_attr("disabled")
                or element.get("aria-disabled") == "true"
            ):
                continue
            href = element.get("href")
            destination = urljoin(target, str(href)) if href else target
            parsed = urlsplit(destination)
            if (
                parsed.scheme != "https"
                or not parsed.hostname
                or parsed.username
                or parsed.password
            ):
                continue
            if re.search(r"/(?:account/)?(?:register|login|sign[-_]?up)(?:/|$)", parsed.path):
                # A portal account gate does not establish an employer application path.
                continue
            # An accessible application control is evidence of a path, not proof of a response.
            level = "application_control"
            if teamtailor:
                if (
                    not supported_url(destination)
                    or "/applications/new" not in urlsplit(destination).path
                ):
                    continue
                if destination not in checked_forms:
                    form_page = await client.get(destination, follow_redirects=False)
                    checked_forms[destination] = form_page.status_code == 200 and _candidate_form(
                        form_page.text
                    )
                if not checked_forms[destination]:
                    continue
                level = "application_form"
            elif _candidate_form(response.text):
                level = "application_form"
            return {
                **result,
                "state": "active",
                "application_url": destination,
                "evidence_level": level,
                "reason": "Accessible listing with an enabled application control",
            }
        result["state"] = "listing_only"
        result["reason"] = (
            "Vacancy page accessible; an open application path could not be confirmed"
        )
    except (httpx.HTTPError, ValueError):
        result["reason"] = "Verification failed temporarily; vacancy status is uncertain"
    return result


class OfferVerificationService:
    async def run(
        self,
        session: Session,
        *,
        limit: int = 20,
        force: bool = False,
        profile_key: str | None = None,
    ) -> dict[str, int]:
        from app.services.ingestion import normalized_from_offer

        repository = JobRepository()
        counts = {"checked": 0, "active": 0, "closed": 0, "unverified": 0, "listing_only": 0}
        if limit <= 0:
            return counts
        keys = [profile_key] if profile_key else list(load_profiles())
        async with httpx.AsyncClient(
            timeout=15,
            headers={"User-Agent": "JobRadar/0.1 (personal vacancy verification)"},
        ) as client:
            for key in keys:
                remaining = limit - counts["checked"]
                if remaining <= 0:
                    break
                if not uses_career_radar(key):
                    continue
                pending = _pending_offers(repository, session, key, force=force)
                try:
                    # Stable top-k keeps the complete existing priority order, including
                    # repository tie order, without retaining all eligible ORM objects.
                    selected = nsmallest(remaining, pending, key=_verification_priority)
                finally:
                    pending.close()
                if not selected:
                    continue
                engine = ScoringEngine(key)
                # The read cursor is closed before checks commit rescored offer changes.
                for offer in selected:
                    result = await verify_listing(client, offer.url, offer.title)
                    offer.raw_payload = {**offer.raw_payload, VERIFICATION_KEY: result}
                    score = engine.score(normalized_from_offer(offer, rehydrate=True))
                    offer.match_score, offer.match_level = score.score, score.level
                    offer.match_reasons = score.match_reasons()
                    offer.negative_reasons = {"negative": score.negative}
                    counts["checked"] += 1
                    counts[result["state"]] += 1
                    session.commit()
                    await asyncio.sleep(1)
        return counts


def _pending_offers(
    repository: JobRepository, session: Session, profile_key: str, *, force: bool,
) -> Generator[JobOffer, None, None]:
    batches = repository.iter_job_batches(
        session,
        JobFilters(profile_key=profile_key, radar="current", min_score=35),
        batch_size=500,
    )
    try:
        for batch in batches:
            for offer in batch:
                if force or (
                    current_verification(offer.raw_payload, offer.url)["state"] == "unverified"
                    and not _checked_recently(offer.raw_payload, offer.url)
                ):
                    yield offer
    finally:
        batches.close()


def _verification_priority(offer: JobOffer) -> tuple[bool, str, int]:
    proof = offer.raw_payload.get(VERIFICATION_KEY)
    checked_at = proof.get("checked_at", "") if isinstance(proof, dict) else ""
    return (
        urlsplit(offer.url or "").hostname
        in {"himalayas.app", "remotive.com", "weworkremotely.com"},
        str(checked_at),
        -offer.match_score,
    )


def _checked_recently(payload: dict[str, Any], url: str | None) -> bool:
    value = payload.get(VERIFICATION_KEY)
    if not isinstance(value, dict):
        return False
    proof = current_verification(payload, url)
    return proof.get("reason") != "Previous verification has expired" and "checked_at" in proof


def _candidate_form(html: str) -> bool:
    soup = BeautifulSoup(html, "html.parser")
    return any(
        form.select_one('input[type="email"]:not([disabled]), input[name*="email"]:not([disabled])')
        is not None
        and form.select_one('input[type="file"]:not([disabled])') is not None
        for form in soup.select("form")
    )


def _bizneo_form(html: str, url: str) -> bool:
    soup = BeautifulSoup(html, "html.parser")
    for form in soup.select('form[method="post"]'):
        action = urlsplit(urljoin(url, str(form.get("action", ""))))
        if (
            action.netloc == urlsplit(url).netloc
            and action.scheme == "https"
            and action.path == "/registration"
            and parse_qs(action.query) == parse_qs(urlsplit(url).query)
            and form.select_one('input[type="email"]:not([disabled])') is not None
            and form.select_one('[data-component-filepicker="box"][name*="[file]"][required]')
            is not None
            and form.select_one('button[type="submit"]:not([disabled])') is not None
        ):
            return True
    return False


def _teamtailor_form(html: str, url: str) -> bool:
    soup = BeautifulSoup(html, "html.parser")
    form = soup.select_one('form#job-application-form[method="post"]')
    if form is None:
        return False
    action = urlsplit(urljoin(url, str(form.get("action", ""))))
    return (
        action.netloc == urlsplit(url).netloc
        and action.scheme == "https"
        and action.path == "/applications"
        and form.select_one('input[type="email"]:not([disabled])') is not None
        and form.select_one('[data-controller~="forms--inputs--upload"]') is not None
        and form.select_one('input[name="candidate[resume_remote_url]"]') is not None
        and form.select_one(
            'input[type="submit"]:not([disabled]), button[type="submit"]:not([disabled])'
        )
        is not None
    )
