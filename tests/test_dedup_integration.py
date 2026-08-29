from __future__ import annotations

import os
from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models.enums import JobStatus, RemoteType
from app.models.job import JobOffer
from app.repositories.jobs import JobRepository
from app.scoring.engine import ScoreResult
from app.services.normalizer import NormalizedJob

pytestmark = pytest.mark.integration


@pytest.fixture()
def pg_session() -> Iterator[Session]:
    url = os.getenv("POSTGRES_TEST_URL")
    if not url:
        pytest.skip("POSTGRES_TEST_URL is required for PostgreSQL integration tests")
    engine = create_engine(url, future=True)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    Base.metadata.drop_all(engine)
    engine.dispose()


def test_upsert_deduplicates_by_canonical_url_and_preserves_status(pg_session: Session) -> None:
    repository = JobRepository()
    source = repository.get_or_create_source(
        pg_session, "fixtures", True, "file://fixtures/jobs.json"
    )
    score = ScoreResult(score=88, level="excellent", positive=["good"], negative=[])
    first = _job(source_job_id="first")
    second = _job(source_job_id="second")

    offer, created = repository.upsert_job(pg_session, source, first, score)
    offer.status = JobStatus.INTERESTED
    pg_session.commit()

    updated_offer, second_created = repository.upsert_job(pg_session, source, second, score)
    pg_session.commit()

    assert created is True
    assert second_created is False
    assert updated_offer.id == offer.id
    assert updated_offer.status == JobStatus.INTERESTED
    assert pg_session.scalar(select(func.count(JobOffer.id))) == 1


def _job(source_job_id: str) -> NormalizedJob:
    return NormalizedJob(
        source_job_id=source_job_id,
        company_name="Nervion Software",
        company_website="https://example.com/nervion",
        title="Backend Java Developer",
        normalized_title="backend java developer",
        description="Java Spring Boot APIs",
        requirements="1 year",
        location="Remote Spain",
        country="Spain",
        remote_type=RemoteType.REMOTE,
        employment_type="full-time",
        experience_min_years=1,
        experience_max_years=1,
        salary_min=30000,
        salary_max=34000,
        salary_currency="EUR",
        salary_period="annual",
        salary_original_text="30,000-34,000 EUR",
        salary_unknown=False,
        url="https://jobs.example.test/backend-java-developer",
        publication_date=datetime.now(UTC),
        expiration_date=None,
        technologies=["Java", "Spring Boot"],
        raw_payload={},
        content_hash="same-hash",
        language="en",
    )
