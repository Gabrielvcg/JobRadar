"""Conservative public-page checks. Never submit applications or bypass access controls."""

from __future__ import annotations

import asyncio
import re
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urljoin, urlsplit

import httpx
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session

from app.core.availability import VERIFICATION_KEY, current_verification
from app.core.profiles import load_profiles, uses_career_radar
from app.repositories.jobs import JobFilters, JobRepository
from app.scoring.engine import ScoringEngine
from app.scoring.evidence import fold
from app.scoring.text import canonical_url

PUBLIC_HOSTS = {
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
}
ATS_SUFFIXES = (".jobs.personio.de", ".jobs.personio.com", ".recruitee.com", ".pinpointhq.com")
CLOSED = re.compile(
    r"\b(?:this (?:job|position|vacancy) (?:is no longer available|has been filled|is closed)|"
    r"no longer accepting applications|job (?:has )?expired|position filled|"
    r"oferta (?:caducada|finalizada|cerrada)|vacante (?:cerrada|cubierta)|"
    r"ya no (?:acepta|se aceptan) (?:solicitudes|candidaturas))\b"
)
APPLY = re.compile(
    r"^(?:apply(?: now| for (?:this|the) (?:job|position)| on company site)?|"
    r"me interesa|i.m interested|solicitar(?: este puesto)?|inscrib\w*|postular\w*|"
    r"enviar cv|submit application)$"
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
            heading = soup.find("h1") or soup.title
            actual = set(re.findall(r"\w+", fold(heading.get_text(" ") if heading else "")))
            if not expected or len(expected & actual) / len(expected) < 0.6:
                result["reason"] = "Page does not confirm the expected vacancy title"
                return result
        for element in soup.select("a[href], button, input[type=submit]"):
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
            # An accessible application control is evidence of a path, not proof of a response.
            return {
                **result,
                "state": "active",
                "application_url": destination,
                "reason": "Accessible listing with an enabled application control",
            }
        result["reason"] = "Page accessible, but no application control could be verified"
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
        counts = {"checked": 0, "active": 0, "closed": 0, "unverified": 0}
        keys = [profile_key] if profile_key else list(load_profiles())
        async with httpx.AsyncClient(
            timeout=15,
            headers={"User-Agent": "JobRadar/0.1 (personal vacancy verification)"},
        ) as client:
            for key in keys:
                if not uses_career_radar(key):
                    continue
                candidates = repository.list_jobs(
                    session,
                    JobFilters(
                        profile_key=key,
                        radar="current",
                        min_score=35,
                        limit=500,
                    ),
                )
                pending = [
                    offer
                    for offer in candidates
                    if force
                    or current_verification(offer.raw_payload, offer.url)["state"] == "unverified"
                ]
                # Access failures are cached too; avoid repeatedly hitting a blocked portal.
                pending = [
                    offer for offer in pending if force or not _checked_recently(offer.raw_payload)
                ]
                pending.sort(
                    key=lambda offer: (
                        urlsplit(offer.url or "").hostname
                        in {"himalayas.app", "remotive.com", "weworkremotely.com"},
                        str(offer.raw_payload.get(VERIFICATION_KEY, {}).get("checked_at", "")),
                        -offer.match_score,
                    )
                )
                engine = ScoringEngine(key)
                for offer in pending[: max(0, limit - counts["checked"])]:
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


def _checked_recently(payload: dict[str, Any]) -> bool:
    value = payload.get(VERIFICATION_KEY)
    if not isinstance(value, dict):
        return False
    proof = current_verification(payload, value.get("listing_url"))
    return proof.get("reason") != "Previous verification has expired" and "checked_at" in proof
