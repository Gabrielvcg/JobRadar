from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest

from app.core.availability import VERIFICATION_KEY, current_verification
from app.scoring.engine import ScoringEngine
from app.services.normalizer import JobNormalizer
from app.services.verification import supported_url, verify_listing
from app.sources.base import RawJob

URL = "https://jobs.smartrecruiters.com/example/123-java-backend"


def check(status: int, body: str, **headers: str) -> dict[str, Any]:
    async def run() -> dict[str, Any]:
        transport = httpx.MockTransport(
            lambda request: httpx.Response(
                status,
                text=body,
                headers=headers,
            )
        )
        async with httpx.AsyncClient(transport=transport) as client:
            return await verify_listing(client, URL, "Java Backend Developer")

    return asyncio.run(run())


def test_active_requires_matching_title_and_application_control() -> None:
    proof = check(200, '<h1>Java Backend Developer</h1><a href="/example/123/apply">Apply now</a>')
    assert proof["state"] == "active"
    assert proof["application_url"] == "https://jobs.smartrecruiters.com/example/123/apply"


@pytest.mark.parametrize(("form_status", "expected"), [(200, "active"), (403, "listing_only")])
def test_teamtailor_checks_candidate_form_without_submitting(
    form_status: int, expected: str
) -> None:
    calls: list[str] = []

    async def run() -> dict[str, Any]:
        def handle(request: httpx.Request) -> httpx.Response:
            assert request.method == "GET"
            calls.append(str(request.url))
            if request.url.path.endswith("/applications/new"):
                return httpx.Response(
                    form_status,
                    text=(
                        '<form><input type="email"><input type="file"><button>Apply</button></form>'
                    ),
                )
            return httpx.Response(
                200,
                text=(
                    "<h1>Java Backend Developer</h1>"
                    '<a href="/jobs/123-java/applications/new">Inscríbete</a>' * 2
                ),
            )

        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
            return await verify_listing(
                client, "https://example.teamtailor.com/jobs/123-java", "Java Backend Developer"
            )

    proof = asyncio.run(run())
    assert proof["state"] == expected
    assert len(calls) == 2
    if expected == "active":
        assert proof["evidence_level"] == "application_form"


def test_greenhouse_board_redirect_is_closed_only_with_official_removal_evidence() -> None:
    async def run() -> dict[str, Any]:
        def handle(request: httpx.Request) -> httpx.Response:
            if request.url.host == "boards-api.greenhouse.io":
                return httpx.Response(404, json={"error": "Job not found"})
            return httpx.Response(200, text="<h1>All open positions</h1>")

        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
            return await verify_listing(
                client,
                "https://job-boards.greenhouse.io/example/jobs/123",
                "Java Backend Developer",
            )

    proof = asyncio.run(run())
    assert proof["state"] == "closed" and proof["evidence_http_status"] == 404


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        ("<h1>Java Backend Developer</h1><button>Apply filters</button>", "listing_only"),
        ('<h1>All jobs</h1><a href="/apply">Apply now</a>', "unverified"),
        ("<h1>Java Backend Developer</h1><button disabled>Apply now</button>", "listing_only"),
        (
            '<h1>Java Backend Developer</h1><button aria-disabled="true">Apply now</button>',
            "listing_only",
        ),
    ],
)
def test_generic_page_or_disabled_control_is_not_verified_active(body: str, expected: str) -> None:
    assert check(200, body)["state"] == expected


def test_smartrecruiters_javascript_control_and_empty_notification_heading() -> None:
    proof = check(
        200,
        '<h1 data-i18n="notification"></h1><h1>Java Backend Developer</h1>'
        '<a class="button js-oneclick" data-sr-track="apply">Me interesa</a>',
    )
    assert proof["state"] == "active"
    assert proof["application_url"] == URL


def test_unbound_anchor_does_not_establish_an_application_path() -> None:
    proof = check(200, "<h1>Java Backend Developer</h1><a>Me interesa</a>")
    assert proof["state"] == "listing_only"


@pytest.mark.parametrize("status", [403, 429, 500])
def test_access_failure_does_not_mean_the_vacancy_closed(status: int) -> None:
    assert check(status, "Access denied")["state"] == "unverified"


@pytest.mark.parametrize("status", [404, 410])
def test_removed_listing_is_closed(status: int) -> None:
    assert check(status, "Not found")["state"] == "closed"


def test_explicit_closed_text_is_not_overridden_by_generic_apply_link() -> None:
    proof = check(
        200,
        "<h1>Java Backend Developer</h1><p>No longer accepting applications</p>"
        '<a href="/apply">Apply now</a>',
    )
    assert proof["state"] == "closed"


def test_redirect_to_unapproved_host_is_not_followed() -> None:
    assert check(302, "", location="http://127.0.0.1/private")["state"] == "unverified"


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost/",
        "https://127.0.0.1/",
        "file:///etc/passwd",
        "https://jobs.smartrecruiters.com:invalid/",
        "https://user:pass@himalayas.app/",
    ],
)
def test_only_public_supported_listing_hosts_are_fetched(url: str) -> None:
    assert supported_url(url) is False


def test_verification_expires_and_cannot_move_to_a_different_vacancy() -> None:
    proof = check(200, "<h1>Java Backend Developer</h1><button>Apply now</button>")
    payload = {VERIFICATION_KEY: proof}
    assert current_verification(payload, URL)["state"] == "active"
    assert current_verification(payload, URL + "-other")["state"] == "unverified"
    proof["checked_at"] = (datetime.now(UTC) - timedelta(hours=25)).isoformat()
    assert current_verification(payload, URL)["state"] == "unverified"


def test_confirmed_closed_offer_is_excluded_without_changing_employment_state() -> None:
    raw = RawJob(
        source_name="fixture",
        source_job_id="proof",
        company_name="Example",
        title="Java Backend Developer",
        description="Build Java Spring Boot APIs with SQL.",
        location="Remote Spain",
        url=URL,
    )
    offer = JobNormalizer().normalize(raw)
    proof = check(410, "Gone")
    result = ScoringEngine().score(replace(offer, raw_payload={VERIFICATION_KEY: proof}))
    assert result.assessment is not None
    assert result.assessment["radar"] == "excluded"
    assert "listing_closed" in result.assessment["blockers"]


@pytest.mark.parametrize(
    "variant,expected",
    [("open", "active"), ("disabled", "listing_only"),
     ("no_upload", "listing_only"), ("different_job", "listing_only")],
)
def test_teamtailor_controller_checks_real_upload_form(variant: str, expected: str) -> None:
    listing = "https://careers.twtspain.com/jobs/123-java-backend"
    calls: list[str] = []

    async def run() -> dict[str, Any]:
        def handle(request: httpx.Request) -> httpx.Response:
            assert request.method == "GET"
            calls.append(str(request.url))
            if request.url.path.endswith("/applications/new"):
                upload = 'data-controller="forms--inputs--upload"' if variant != "no_upload" else ""
                disabled = "disabled" if variant == "disabled" else ""
                return httpx.Response(200, text=(
                    '<form id="job-application-form" method="post" action="/applications">'
                    '<input type="email" name="candidate[email]">'
                    f'<div {upload}><input name="candidate[resume_remote_url]" disabled></div>'
                    f'<input type="submit" value="Enviar solicitud" {disabled}></form>'
                ))
            path = listing if variant != "different_job" else listing.replace("123", "456")
            return httpx.Response(200, text=(
                '<h1>Java Backend Developer</h1>'
                '<main data-careersite--jobs--form-overlay-job-application-url-value="'
                + path + '/applications/new"><button disabled>Enviar solicitud</button></main>'
            ))

        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
            return await verify_listing(client, listing, "Java Backend Developer")

    proof = asyncio.run(run())
    assert proof["state"] == expected
    assert len(calls) == (1 if variant == "different_job" else 2)
    if expected == "active":
        assert proof["application_url"] == listing + "/applications/new"
        assert proof["evidence_level"] == "application_form"
