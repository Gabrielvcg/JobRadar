from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx
import pytest

from app.models.enums import RemoteType
from app.sources.base import SearchConfig
from app.sources.jazzhr import JazzHrJobSource

SEARCH = SearchConfig(["java"], [], [], [], [])


def _posting(**extra: Any) -> str:
    data = {
        "@type": "JobPosting",
        "title": "Java Backend Developer",
        "description": "<p>Develop Java Spring Boot APIs.</p><p>Salario hasta 33k.</p>",
        "datePosted": "2026-10-05",
        "validThrough": "2027-01-03",
        "employmentType": "FULL_TIME",
        "jobLocationType": "TELECOMMUTE",
        "applicantLocationRequirements": {"@type": "Country", "name": "ES"},
        **extra,
    }
    return (
        f'<script type="application/ld+json">{json.dumps(data)}</script>'
        '<form><input name="secret" value="hidden-secret"><textarea>Private CV</textarea></form>'
        '<div id="job-application-form-container">Recruiter private contact</div>'
    )


def test_structured_mapping_and_private_application_fields_are_not_retained() -> None:
    source = JazzHrJobSource({"company_name": "IRIUM"})
    job = source._to_job(_posting(), "https://iriumspain.applytojob.com/apply/ID/Java", "ID")
    assert job is not None
    assert job.title == "Java Backend Developer"
    assert job.country == "Spain"
    assert job.remote_type == RemoteType.REMOTE
    assert job.publication_date and job.publication_date.year == 2026
    assert job.expiration_date and job.expiration_date.year == 2027
    assert job.salary_original_text == "Salario hasta 33k."
    assert job.source_job_id == "iriumspain.applytojob.com:ID"
    assert job.company_name == "IRIUM"
    stored = json.dumps(job.raw_payload)
    assert all(value not in stored for value in ["hidden-secret", "Private CV", "private contact"])


def test_html_fallback_does_not_invent_location_or_capture_form() -> None:
    source = JazzHrJobSource({})
    job = source._to_job(
        '<h1>Backend Java</h1><div id="job-description"><p>Build Java APIs.</p>'
        '<form>Private CV<input value="secret"></form></div>',
        "https://iriumspain.applytojob.com/apply/ID/Java",
        "ID",
    )
    assert job and job.title == "Backend Java"
    assert job.location is None and job.country is None
    assert job.publication_date is None and job.remote_type == RemoteType.UNKNOWN
    assert "Private CV" not in job.description
    assert "secret" not in json.dumps(job.raw_payload)


def test_public_board_only_and_request_bounds_filter_links_before_detail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests: list[str] = []
    waits: list[float] = []

    async def no_wait(delay: float) -> None:
        waits.append(delay)

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(str(request.url))
        if request.url.path == "/":
            links = "".join(
                f'<a href="/apply/J{i}/Java?tracking=x">Java Developer {i}</a>' for i in range(15)
            )
            return httpx.Response(
                200,
                text=links
                + '<a href="/apply/J0/Java">Java duplicate</a>'
                + '<a href="/apply/HR/Recruiter">Recruiter</a>'
                + '<a href="/cb/secret">Java callback</a>'
                + '<a href="https://evil.invalid/apply/ID/Java">Java Engineer</a>'
                + '<a href="/apply/ID/Java?bad=x"><form>hidden</form></a>',
            )
        return httpx.Response(
            200,
            text=_posting(title=f"Java Backend {request.url.path}", description=request.url.path),
        )

    real = httpx.AsyncClient
    monkeypatch.setattr(
        httpx, "AsyncClient", lambda **kw: real(**kw, transport=httpx.MockTransport(handler))
    )
    monkeypatch.setattr("app.sources.jazzhr.asyncio.sleep", no_wait)
    source = JazzHrJobSource({"max_details_per_company": 99, "rate_limit_seconds": 0})
    jobs = asyncio.run(source.fetch_jobs(SEARCH))
    assert len(requests) == 11
    assert len(jobs) == 10
    assert len(waits) == 11 and min(waits) >= 1
    assert source.min_interval_minutes >= 720
    assert all("?" not in url and "evil.invalid" not in url for url in requests)
    assert all("Recruiter" not in url and "/cb/" not in url for url in requests)


@pytest.mark.parametrize("status", [403, 404, 410, 429])
def test_access_blocks_and_removed_boards_are_not_retried(
    monkeypatch: pytest.MonkeyPatch, status: int
) -> None:
    calls: list[str] = []

    async def run() -> list[Any]:
        async def no_wait(delay: float) -> None:
            pass

        monkeypatch.setattr("app.sources.jazzhr.asyncio.sleep", no_wait)

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(str(request.url))
            return httpx.Response(status)

        real = httpx.AsyncClient
        monkeypatch.setattr(
            httpx, "AsyncClient", lambda **kw: real(**kw, transport=httpx.MockTransport(handler))
        )
        return await JazzHrJobSource({"retries": 99}).fetch_jobs(SEARCH)

    assert asyncio.run(run()) == []
    assert len(calls) == 1


def test_transient_retries_bounded_and_external_redirect_not_followed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    async def no_wait(delay: float) -> None:
        pass

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        if len(calls) < 3:
            return httpx.Response(503)
        return httpx.Response(302, headers={"location": "https://private.invalid/cb/secret"})

    real = httpx.AsyncClient
    monkeypatch.setattr(
        httpx, "AsyncClient", lambda **kw: real(**kw, transport=httpx.MockTransport(handler))
    )
    monkeypatch.setattr("app.sources.jazzhr.asyncio.sleep", no_wait)
    assert asyncio.run(JazzHrJobSource({"retries": 99}).fetch_jobs(SEARCH)) == []
    assert len(calls) == 3 and all("private.invalid" not in url for url in calls)


@pytest.mark.parametrize("url", ["http://iriumspain.applytojob.com", "https://evil.invalid"])
def test_unsupported_board_rejected(url: str) -> None:
    with pytest.raises(ValueError, match="HTTPS applytojob.com"):
        JazzHrJobSource({"base_url": url})
