"""Portable repository/HTTP checks; PostgreSQL-specific checks remain separate."""

from __future__ import annotations

import asyncio
import csv
import io
from collections.abc import Iterator
from dataclasses import replace
from datetime import UTC, date, datetime
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api import routes
from app.core.availability import VERIFICATION_KEY
from app.core.offer_identity import ORIGINS_KEY
from app.db.base import Base
from app.db.session import get_session
from app.main import app
from app.models.enums import JobStatus, RemoteType
from app.models.job import JobOffer, User
from app.repositories.jobs import JobFilters, JobRepository
from app.scoring.engine import ScoringEngine
from app.services.ingestion import IngestionService, _all_jobs_filter
from app.services.normalizer import JobNormalizer
from app.sources.base import RawJob, SearchConfig
from app.sources.smartrecruiters import SmartRecruitersJobSource


@compiles(JSONB, "sqlite")
def sqlite_json(type_: Any, compiler: Any, **kw: Any) -> str:
    return "JSON"


@pytest.fixture()
def session() -> Iterator[Session]:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as value:
        yield value
    engine.dispose()


def persist(session: Session, title: str, identity: str) -> JobOffer:
    repository = JobRepository()
    source = repository.get_or_create_source(session, "synthetic", True, None)
    raw = RawJob(
        source_name="synthetic",
        source_job_id=identity,
        company_name="Example",
        title=title,
        description="Build Java Spring Boot REST APIs with SQL and Docker.",
        requirements="2 years of experience",
        location="Remote Spain",
        country="Spain",
        remote_type=RemoteType.REMOTE,
        url=f"https://example.test/jobs/{identity}",
        publication_date=datetime(2026, 10, 20, tzinfo=UTC),
    )
    normalized = JobNormalizer().normalize(raw)
    score = ScoringEngine(as_of=date(2026, 10, 21)).score(normalized)
    offer, _ = repository.upsert_job(session, source, normalized, score)
    session.commit()
    return offer


def test_complete_csv_includes_disabled_history_and_full_review_evidence(
    session: Session, monkeypatch: pytest.MonkeyPatch,
) -> None:
    offer = persist(session, "Java Backend", "export-active")
    offer.description = "Backend description, with commas\nand multiple lines."
    offer.source.enabled = False
    session.commit()
    app.dependency_overrides[get_session] = lambda: session
    monkeypatch.setattr(routes, "get_current_user", lambda request, session: None)
    try:
        with TestClient(app) as client:
            normal = client.get("/jobs/export?profile=engineering&radar=all")
            complete = client.get(
                "/jobs/export?profile=engineering&radar=all&include_disabled_sources=true"
            )
        assert not list(csv.DictReader(io.StringIO(normal.text.lstrip("\ufeff"))))
        rows = list(csv.DictReader(io.StringIO(complete.text.lstrip("\ufeff"))))
        assert len(rows) == 1
        assert rows[0]["description"] == offer.description
        assert rows[0]["requirements"] == "2 years of experience"
        assert rows[0]["source_enabled"] == "False"
        assert rows[0]["recommendation"] == "U"
        assert rows[0]["availability_state"] == "unverified"
    finally:
        app.dependency_overrides.clear()


def test_assessment_roundtrip_and_radar_filter_before_pagination(session: Session) -> None:
    current = persist(session, "Java Backend Developer", "current")
    strategic = persist(session, "Senior Java Developer", "future")
    repository = JobRepository()
    assert repository.list_jobs(session, JobFilters(radar="current", limit=1)) == [current]
    assert repository.list_jobs(session, JobFilters(radar="strategic")) == [strategic]
    assert repository.list_jobs(session, JobFilters(category="C")) == [strategic]
    assert repository.stats(session, profile_key="engineering", radar="current")["total"] == 1
    assert current.match_reasons["assessment"]["professional_months"] == 14


def test_daily_refresh_recalculates_once_and_preserves_user_status(session: Session) -> None:
    offer = persist(session, "Java Backend Developer", "refresh")
    offer.status = JobStatus.INTERESTED
    assessment = dict(offer.match_reasons["assessment"], evaluated_on="2020-01-01")
    offer.match_reasons = {**offer.match_reasons, "assessment": assessment}
    session.commit()
    service = IngestionService()
    assert service.score_all_jobs(session, only_stale=True) == 1
    assert service.score_all_jobs(session, only_stale=True) == 0
    assert offer.status == JobStatus.INTERESTED
    assert _all_jobs_filter().sort == "id"


def test_equal_scores_prefer_actionable_advice_over_missing_information(session: Session) -> None:
    ambitious = persist(session, "Java Backend Services", "ambitious")
    uncertain = persist(session, "Java Backend Integrations", "uncertain")
    for offer, advice in ((ambitious, "B"), (uncertain, "U")):
        offer.match_score = 64
        assessment = dict(offer.match_reasons["assessment"], recommendation=advice)
        offer.match_reasons = {**offer.match_reasons, "assessment": assessment}
    session.commit()
    assert JobRepository().list_jobs(session, JobFilters(limit=2)) == [ambitious, uncertain]


def test_duplicate_across_sources_with_tracking_url_keeps_status(session: Session) -> None:
    offer = persist(session, "Java Backend Developer", "duplicate")
    offer.status = JobStatus.APPLIED
    repository = JobRepository()
    source = repository.get_or_create_source(session, "second", True, None)
    raw = RawJob(
        source_name="second",
        source_job_id="another",
        company_name="Example",
        title="Java Backend Developer",
        description="Different portal description",
        url="https://example.test/jobs/duplicate?utm_source=second",
    )
    normalized = JobNormalizer().normalize(raw)
    updated, created = repository.upsert_job(
        session, source, normalized, ScoringEngine().score(normalized)
    )
    assert not created and updated.id == offer.id
    assert updated.status == JobStatus.APPLIED


def test_employer_promotes_mirror_keeps_alias_and_blocks_stale_portal_updates(
    session: Session,
) -> None:
    repo = JobRepository()
    portal = repo.get_or_create_source(session, "himalayas", True, None)
    employer = repo.get_or_create_source(session, "knowmad_official", True, None)
    raw = RawJob(
        source_name="himalayas",
        source_job_id="portal-id",
        company_name="Example",
        title="Java Backend Developer",
        location="Spain",
        country="Spain",
        remote_type=RemoteType.REMOTE,
        url="https://himalayas.app/companies/example/jobs/java",
        description=(
            "Build Java Spring Boot REST APIs with SQL and Docker. "
            "Collaborate with QA and architecture teams on reliable services. "
            "Required: 2 years of backend development experience."
        ),
    )
    mirror = JobNormalizer().normalize(raw)
    offer, _ = repo.upsert_job(session, portal, mirror, ScoringEngine().score(mirror))
    offer.status = JobStatus.APPLIED
    original_id = offer.id
    official = JobNormalizer().normalize(
        replace(
            raw,
            source_name="knowmad_official",
            source_job_id="employer-id",
            url="https://example.teamtailor.com/jobs/123-java",
            location="Sevilla, Spain",
        )
    )
    promoted, created = repo.upsert_job(
        session, employer, official, ScoringEngine().score(official)
    )
    assert not created and promoted.id == original_id and promoted.status == JobStatus.APPLIED
    assert promoted.source.name == "knowmad_official"
    assert promoted.raw_payload[ORIGINS_KEY]["himalayas"]["source_job_id"] == "portal-id"
    promoted.raw_payload = {**promoted.raw_payload, VERIFICATION_KEY: {"state": "closed"}}
    session.commit()
    assert repo.find_existing(session, portal, mirror) is promoted
    seen, created = repo.upsert_job(session, portal, mirror, ScoringEngine().score(mirror))
    assert not created and seen.url == official.url
    assert seen.raw_payload[VERIFICATION_KEY]["state"] == "closed"
    assert seen.status == JobStatus.APPLIED


def test_mirror_matching_does_not_merge_different_requirement_numbers(session: Session) -> None:
    repo = JobRepository()
    portal = repo.get_or_create_source(session, "himalayas", True, None)
    official = repo.get_or_create_source(session, "knowmad_official", True, None)
    raw = RawJob(
        source_name="himalayas",
        source_job_id="mirror",
        company_name="Example",
        title="Java Backend Developer",
        location="Spain",
        url="https://himalayas.app/jobs/java",
        description="Build Java Spring Boot REST APIs and services with SQL. " * 3
        + "Required: 2 years of Java experience.",
    )
    normalized = JobNormalizer().normalize(raw)
    repo.upsert_job(session, portal, normalized, ScoringEngine().score(normalized))
    other = JobNormalizer().normalize(
        replace(
            raw,
            source_name="knowmad_official",
            source_job_id="other",
            url="https://example.teamtailor.com/jobs/321-java",
            description=raw.description.replace("2 years", "5 years"),
        )
    )
    assert repo.find_existing(session, official, other) is None


@pytest.mark.parametrize("office_location", ["Barcelona, Spain", "Spain"])
def test_mirror_matching_does_not_transfer_state_to_an_office_role(
    session: Session,
    office_location: str,
) -> None:
    repo = JobRepository()
    portal = repo.get_or_create_source(session, "himalayas", True, None)
    employer = repo.get_or_create_source(session, "official", True, None)
    raw = RawJob(
        source_name="himalayas",
        source_job_id="remote",
        company_name="Example",
        title="Java Backend Developer",
        location="Spain",
        country="Spain",
        remote_type=RemoteType.REMOTE,
        url="https://himalayas.app/jobs/java",
        description="Build Java Spring Boot REST APIs and services with SQL. " * 3,
    )
    normalized = JobNormalizer().normalize(raw)
    offer, _ = repo.upsert_job(session, portal, normalized, ScoringEngine().score(normalized))
    offer.status = JobStatus.APPLIED
    onsite = JobNormalizer().normalize(
        replace(
            raw,
            source_name="official",
            source_job_id="barcelona",
            location=office_location,
            remote_type=RemoteType.HYBRID,
            url="https://example.teamtailor.com/jobs/office-java",
        )
    )
    assert repo.find_existing(session, employer, onsite) is None


def test_verification_roundtrip_caches_failures_and_preserves_application_state(
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.services import verification

    first = persist(session, "Java Backend Developer", "open")
    second = persist(session, "Backend Java Engineer", "closed")
    first.status = JobStatus.INTERESTED
    calls: list[str] = []

    async def fake_check(client: Any, url: str, title: str) -> dict[str, Any]:
        calls.append(url)
        return {
            "state": "closed" if url.endswith("closed") else "active",
            "listing_url": url,
            "checked_at": datetime.now(UTC).isoformat(),
            "application_url": url + "/apply",
            "reason": "Synthetic page evidence",
        }

    async def no_wait(*args: Any) -> None:
        return None

    monkeypatch.setattr(verification, "verify_listing", fake_check)
    monkeypatch.setattr(verification.asyncio, "sleep", no_wait)
    result = asyncio.run(verification.OfferVerificationService().run(session))
    assert result["checked"] == 2 and result["active"] == 1 and result["closed"] == 1
    assert first.status == JobStatus.INTERESTED
    assert first.raw_payload[VERIFICATION_KEY]["state"] == "active"
    assert JobRepository().list_jobs(session, JobFilters(verified_only=True)) == [first]
    assert second.match_reasons["assessment"]["radar"] == "excluded"
    assert asyncio.run(verification.OfferVerificationService().run(session))["checked"] == 0
    assert len(calls) == 2
    assert first.url is not None
    first.url += "-canonical"
    session.commit()
    assert asyncio.run(verification.OfferVerificationService().run(session))["checked"] == 1
    assert calls[-1] == first.url
    assert first.status == JobStatus.INTERESTED


def test_rescore_restores_original_html_boundaries(session: Session) -> None:
    offer = persist(session, "Java Backend Developer", "legacy-html")
    offer.description = "Required 2 years Java experience Preferred 8 years AWS experience"
    offer.requirements = None
    offer.raw_payload = {
        "description": "<p>Required: 2 years of Java experience.</p>"
        "<p>Preferred: 8 years of AWS experience.</p>"
    }
    session.commit()
    IngestionService().score_all_jobs(session)
    evidence = offer.match_reasons["assessment"]["experience_requirements"]
    assert [item["kind"] for item in evidence] == ["mandatory", "desirable"]
    assert offer.experience_min_years == 2


def test_rescore_recovers_salary_ceiling_without_guaranteeing_minimum(session: Session) -> None:
    offer = persist(session, "Java Backend Developer", "ceiling")
    offer.description = "Build Java Spring Boot APIs. Salario hasta 33K."
    offer.salary_min = offer.salary_max = 33000
    offer.salary_unknown = False
    session.commit()
    IngestionService().score_all_jobs(session)
    assert offer.salary_min is None and offer.salary_max == 33000
    assert offer.match_reasons["assessment"]["salary_status"] == "overlapping_minimum"


def test_http_and_dashboard_keep_assessment_and_separate_radars(
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    persist(session, "Java Backend Developer", "current")
    persist(session, "Senior Java Developer", "future")
    app.dependency_overrides[get_session] = lambda: session
    monkeypatch.setattr(
        routes,
        "get_current_user",
        lambda *args: User(
            id=1, email="example@test.invalid", display_name="Example", is_admin=False
        ),
    )
    try:
        with TestClient(app) as client:
            response = client.get("/jobs")
            assert response.status_code == 200
            assert len(response.json()["items"]) == 1
            assert response.json()["items"][0]["career_assessment"]["category"] == "A"
            assert len(client.get("/jobs?radar=strategic").json()["items"]) == 1
            assert len(client.get("/jobs?radar=all").json()["items"]) == 2
            assert client.get("/jobs/stats").json()["total"] == 1
            assert client.get("/jobs?radar=invalid").status_code == 422
            page = client.get("/?radar=strategic&min_score=0&category=")
            assert page.status_code == 200
            assert "Senior Java Developer" in page.text
            assert "Heuristic scores" in page.text
    finally:
        app.dependency_overrides.clear()


def test_smartrecruiters_mapping_request_bounds_and_active_public_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path.endswith("/postings"):
            assert request.url.params["q"] == "Java"
            assert request.url.params["country"] == "es"
            return httpx.Response(200, json={"content": [{"id": "1"}, {"id": "2"}, {"id": "3"}]})
        return httpx.Response(
            200,
            json={
                "id": request.url.path[-1],
                "name": "Java Backend Developer",
                "postingUrl": "https://jobs.smartrecruiters.com/example/1-java-backend",
                "applyUrl": "https://jobs.smartrecruiters.com/example/1-java-backend?oga=true",
                "active": request.url.path[-1] != "2",
                "creator": {"email": "private@test.invalid"},
                "location": {"city": "Sevilla", "country": "es", "hybrid": True},
                "jobAd": {
                    "sections": {
                        "jobDescription": {"text": "Build Java APIs"},
                        "qualifications": {"text": "2 years of Java experience"},
                    }
                },
            },
        )

    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        httpx, "AsyncClient", lambda **kw: real_client(**kw, transport=httpx.MockTransport(handle))
    )
    source = SmartRecruitersJobSource(
        {
            "companies": ["example"],
            "rate_limit_seconds": 0,
            "required_any_keywords": ["java"],
            "max_details_per_company": 2,
        }
    )
    jobs = asyncio.run(source.fetch_jobs(SearchConfig([], [], [], [], [])))
    assert len(requests) == 3
    assert len(jobs) == 1
    assert jobs and jobs[0].remote_type == RemoteType.HYBRID
    assert jobs[0].country == "Spain"
    assert "creator" not in jobs[0].raw_payload
    assert jobs[0].requirements == "2 years of Java experience"
    assert jobs[0].url == "https://jobs.smartrecruiters.com/example/1-java-backend"
