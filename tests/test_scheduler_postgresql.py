"""Disposable PostgreSQL release gates; never use a production database."""

from __future__ import annotations

import asyncio
import os
import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy import create_engine, delete, event, select
from sqlalchemy.orm import Session

from app.core.availability import VERIFICATION_KEY
from app.db.base import Base
from app.models.job import Company, JobOffer, JobSource
from app.repositories.jobs import JobRepository
from app.scoring.engine import ScoreResult
from app.services import verification


@pytest.mark.integration
def test_postgresql_scheduler_scans_past_500_and_closes_before_commits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    url = os.getenv("JOBRADAR_SCHEDULER_TEST_POSTGRES_URL")
    if not url:
        pytest.skip("Dedicated disposable scheduler database is required")
    engine = create_engine(url)
    key = "scheduler-test-" + uuid.uuid4().hex
    calls: list[str] = []
    cursors = []
    source_id = company_id = None

    @event.listens_for(engine, "after_cursor_execute")
    def capture(
        connection: Any, cursor: Any, statement: Any, parameters: Any,
        context: Any, many: Any,
    ) -> None:
        if context.execution_options.get("yield_per"):
            cursors.append(cursor)

    class Scorer:
        def __init__(self, profile: str) -> None:
            assert profile == key

        def score(self, job: Any) -> ScoreResult:
            return ScoreResult(
                score=0, level="low", positive=[], negative=[], assessment={"radar": "excluded"},
            )

    async def check(client: Any, url: str, title: str) -> dict[str, Any]:
        assert len(cursors) == 1 and cursors[0].name and cursors[0].closed
        calls.append(url)
        return {"state": "active", "listing_url": url, "checked_at": datetime.now(UTC).isoformat()}

    async def sleep(delay: float) -> None:
        pass

    monkeypatch.setattr(verification, "uses_career_radar", lambda profile: profile == key)
    monkeypatch.setattr(verification, "ScoringEngine", Scorer)
    monkeypatch.setattr(verification, "verify_listing", check)
    monkeypatch.setattr(verification.asyncio, "sleep", sleep)
    try:
        Base.metadata.create_all(engine)
        with Session(engine) as session:
            source = JobSource(name=key, profile_key=key, enabled=True)
            company = Company(name=key)
            session.add_all([source, company])
            session.flush()
            source_id, company_id = source.id, company.id
            now = datetime.now(UTC).isoformat()
            for index in range(1003):
                link = f"https://jobs.lever.co/synthetic/{key}/{index}"
                raw: dict[str, Any] = {VERIFICATION_KEY: {
                    "state": "active", "listing_url": link, "checked_at": now,
                }} if index < 1001 else {VERIFICATION_KEY: []}
                session.add(JobOffer(
                    source=source, company=company, profile_key=key, source_job_id=str(index),
                    title="Synthetic", normalized_title="synthetic", description="Offline PG gate",
                    url=link, content_hash=str(index), match_score=70 if index < 1001 else 35,
                    raw_payload=raw, match_reasons={"assessment": {"radar": "current"}},
                ))
            session.commit()
            result = asyncio.run(verification.OfferVerificationService().run(
                session, limit=2, profile_key=key,
            ))
            assert result["checked"] == 2 and len(set(calls)) == 2
            assert all(url.rsplit("/", 1)[1] in {"1001", "1002"} for url in calls)
        with Session(engine) as session:
            changed = list(session.scalars(select(JobOffer).where(
                JobOffer.profile_key == key, JobOffer.match_score == 0,
            )))
            assert len(changed) == 2
            assert all(row.raw_payload[VERIFICATION_KEY]["state"] == "active" for row in changed)
    finally:
        if source_id is not None:
            with Session(engine) as session:
                session.execute(delete(JobOffer).where(JobOffer.profile_key == key))
                session.execute(delete(JobSource).where(JobSource.id == source_id))
                session.execute(delete(Company).where(Company.id == company_id))
                session.commit()
        engine.dispose()


@pytest.mark.integration
def test_postgresql_scheduler_closes_named_cursor_on_read_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    url = os.getenv("JOBRADAR_SCHEDULER_TEST_POSTGRES_URL")
    if not url:
        pytest.skip("Dedicated disposable scheduler database is required")
    # Use a rollback-only transaction to leave no synthetic rows after this failure test.
    engine = create_engine(url)
    cursors = []

    @event.listens_for(engine, "after_cursor_execute")
    def capture(
        connection: Any, cursor: Any, statement: Any, parameters: Any,
        context: Any, many: Any,
    ) -> None:
        if context.execution_options.get("yield_per"):
            cursors.append(cursor)

    def fail(*args: Any) -> Any:
        raise RuntimeError("synthetic reader failure")

    monkeypatch.setattr(verification, "current_verification", fail)
    try:
        Base.metadata.create_all(engine)
        with engine.connect() as connection, connection.begin() as transaction:
            with Session(bind=connection) as session:
                key = uuid.uuid4().hex
                source = JobSource(name=key, profile_key=key, enabled=True)
                company = Company(name=key)
                session.add_all([source, company])
                session.flush()
                session.add(JobOffer(
                    source=source, company=company, profile_key=key, title="Synthetic",
                    normalized_title="synthetic", description="Offline PG gate", content_hash=key,
                    match_score=70, match_reasons={"assessment": {"radar": "current"}},
                ))
                session.flush()
                pending = verification._pending_offers(JobRepository(), session, key, force=False)
                with pytest.raises(RuntimeError, match="synthetic reader failure"):
                    next(pending)
                assert len(cursors) == 1 and cursors[0].name and cursors[0].closed
            transaction.rollback()
    finally:
        engine.dispose()
