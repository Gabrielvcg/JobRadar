from __future__ import annotations

import asyncio
from pathlib import Path

import httpx
import pytest

from app.models.enums import RemoteType
from app.sources.base import RawJob, SearchConfig
from app.sources.zoho import ZohoRssJobSource, public_job

HOST = "https://globalhumancapitalgroup.zohorecruit.com"
FIXTURES = Path(__file__).parent / "fixtures"


def source() -> ZohoRssJobSource:
    return ZohoRssJobSource(
        "ghcg_official",
        {
            "base_url": HOST + "/jobs/Careers/rss",
            "company_name": "Global Human Capital Group",
            "required_any_keywords": ["java"],
            "title_required_any_keywords": ["java"],
            "description_fields": ["Job_Description", "Funciones_Responsabilidades"],
            "requirement_fields": ["Requisitos"],
            "rate_limit_seconds": 0,
        },
    )


def test_real_junior_keeps_requirements_and_duties_missing_from_rss() -> None:
    text = (FIXTURES / "zoho-ghcg-junior.html").read_text(encoding="utf-8")
    title = "Junior Java | Spring developer (Remote Work in Spain)"
    raw = RawJob(
        source_name="ghcg_official",
        source_job_id=None,
        company_name="Global Human Capital Group",
        title=title,
        description="RSS excerpt",
        remote_type=RemoteType.REMOTE,
        url=HOST + "/jobs/Careers/353577000030011001/Junior-Java",
    )
    job = source()._enrich(raw, text)
    assert "Design, develop, debug" in job.description
    assert "B2 an absolute minimum" in (job.requirements or "")
    assert "Bonus skills" in (job.requirements or "")
    assert "1-2 year experience" in (job.requirements or "")
    assert "structured): 1-3 years" in (job.requirements or "")
    assert job.country == "España"
    assert job.remote_type == RemoteType.UNKNOWN
    assert job.source_job_id == "353577000030011001"


def test_real_senior_keeps_conflicting_experience_and_optional_cloud() -> None:
    text = (FIXTURES / "zoho-ghcg-senior.html").read_text(encoding="utf-8")
    data = public_job(text, "353577000029620067")
    assert "Minimum 2-3 year" in data["Requisitos"]
    assert data["Work_Experience"] == "4-5 años"
    assert "Minimum 3 yr" in data["Job_Description"]
    assert "Bonus skills:" in data["Requisitos"]
    assert "Experience with cloud vendor APIs" in data["Requisitos"]


def test_wrong_identity_or_missing_data_is_rejected() -> None:
    text = (FIXTURES / "zoho-ghcg-junior.html").read_text(encoding="utf-8")
    with pytest.raises(ValueError, match="identity"):
        public_job(text, "999")
    with pytest.raises(ValueError, match="no public job data"):
        public_job("<html>Job was removed</html>", "353577000030011001")
    with pytest.raises(ValueError, match="title"):
        source()._enrich(
            RawJob(
                source_name="ghcg_official",
                source_job_id=None,
                company_name="GHCG",
                title="Different job",
                description="Java",
                url=HOST + "/jobs/Careers/353577000030011001/Other",
            ),
            text,
        )


def test_detail_requests_cannot_leave_configured_employer_host() -> None:
    for url in [
        "https://other.zohorecruit.com/jobs/Careers/123/Job",
        HOST + ".evil.test/jobs/Careers/123/Job",
        "http://globalhumancapitalgroup.zohorecruit.com/jobs/Careers/123/Job",
    ]:
        with pytest.raises(ValueError, match="host"):
            source()._job_id(url)


def test_public_feed_filters_before_detail_requests(monkeypatch: pytest.MonkeyPatch) -> None:
    title = "Junior Java | Spring developer (Remote Work in Spain)"
    path = "/jobs/Careers/353577000030011001/Junior-Java"
    rss = f"""<rss><channel><item><title>{title}</title><link>{HOST}{path}</link>
    <description>Java backend Spain</description></item><item><title>Nurse</title>
    <link>{HOST}/jobs/Careers/999/Nurse</link><description>Healthcare</description>
    </item></channel></rss>"""
    requested = []

    def respond(request: httpx.Request) -> httpx.Response:
        requested.append(request.url.path)
        text = (
            rss
            if request.url.path.endswith("/rss")
            else (FIXTURES / "zoho-ghcg-junior.html").read_text(encoding="utf-8")
        )
        return httpx.Response(200, text=text)

    client_class = httpx.AsyncClient
    transport = httpx.MockTransport(respond)
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: client_class(transport=transport, **kw))
    jobs = asyncio.run(
        source().fetch_jobs(
            SearchConfig(
                queries=["java"],
                countries=["Spain"],
                cities=[],
                remote_from=["Spain"],
                languages=[],
            )
        )
    )
    assert len(jobs) == 1
    assert requested == ["/jobs/Careers/rss", path]
