"""Cross-surface personal status contract; SQLite and direct route invocation."""

from __future__ import annotations

import csv
import io
import uuid
from collections import Counter
from collections.abc import Iterator
from datetime import UTC, datetime
from itertools import product
from typing import Any

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session
from starlette.requests import Request
from starlette.responses import Response

from app.api import routes
from app.db.base import Base
from app.models.enums import JobStatus, RemoteType
from app.models.job import Company, JobOffer, JobSource, User, UserJobState
from app.repositories.jobs import JobFilters, JobRepository


class ContextResponse(Response):
    def __init__(self, context: dict[str, Any]) -> None:
        super().__init__()
        self.context = context


@compiles(JSONB, "sqlite")
def sqlite_json(type_: Any, compiler: Any, **kw: Any) -> str:
    return "JSON"


@pytest.fixture()
def session() -> Iterator[Session]:
    engine = create_engine("sqlite://")

    @event.listens_for(engine, "connect")
    def foreign_keys(connection: Any, record: Any) -> None:
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as value:
        yield value
    engine.dispose()


def list_route(session: Session, status: JobStatus | None = None) -> Any:
    return routes.list_jobs(
        request=Request({"type": "http"}), session=session, min_score=None, match_level=None,
        technology=None, source=None, company=None, salary_min=None, salary_known=False,
        remote_type=None, status_filter=status, published_after=None, q=None,
        profile="engineering", radar="all", category=None, verified_only=False,
        sort="score", order="desc", limit=200, offset=0,
    )


def prepare(session: Session, shared: JobStatus) -> tuple[list[User], dict[str, Any]]:
    owners = [
        User(email=f"owner{i}@example.invalid", display_name=f"Owner {i}", password_hash="fake")
        for i in range(2)
    ]
    source = JobSource(name="synthetic", enabled=True, profile_key="engineering")
    company = Company(name="Synthetic")
    session.add_all([source, company, *owners])
    session.flush()
    expected: dict[str, Any] = {}
    now = datetime(2026, 10, 24, 12, tzinfo=UTC)
    for i, states in enumerate(product([None, *JobStatus], repeat=2)):
        offer = JobOffer(
            id=uuid.UUID(int=(0xAB << 120) + i + 1), source_id=source.id,
            company_id=company.id, source_job_id=str(i), profile_key="engineering",
            title=f"Synthetic Java {i}", normalized_title=f"synthetic java {i}",
            description="Synthetic personal-state contract.", url=f"https://example.invalid/{i}",
            remote_type=RemoteType.REMOTE, technologies=[], raw_payload={},
            match_reasons={}, negative_reasons={}, content_hash=f"{i:064x}",
            match_score=70, match_level="good", salary_unknown=True, status=shared,
            first_seen_at=now, last_seen_at=now, created_at=now, updated_at=now,
        )
        session.add(offer)
        session.flush()
        for owner, state in zip(owners, states, strict=True):
            if state is not None:
                session.add(UserJobState(user_id=owner.id, job_offer_id=offer.id, status=state))
        expected[str(offer.id)] = states
    session.commit()
    return owners, expected


def state_snapshot(session: Session) -> list[Any]:
    return list(session.execute(
        select(UserJobState.user_id, UserJobState.job_offer_id, UserJobState.status)
        .order_by(UserJobState.user_id, UserJobState.job_offer_id)
    ))


@pytest.mark.parametrize("shared", list(JobStatus))
def test_personal_state_agrees_across_surfaces_and_owners(
    session: Session, monkeypatch: pytest.MonkeyPatch, shared: JobStatus,
) -> None:
    owners, combinations = prepare(session, shared)
    repository = JobRepository()
    before = state_snapshot(session)
    differences: list[str] = []
    captured: dict[str, str] = {}
    response_factory = routes.StreamingResponse

    def capture_response(content: Any, **kwargs: Any) -> Any:
        chunks = list(content)
        captured["csv"] = "".join(chunks)
        return response_factory(iter(chunks), **kwargs)

    monkeypatch.setattr(routes, "StreamingResponse", capture_response)
    monkeypatch.setattr(
        routes.templates, "TemplateResponse",
        lambda **kwargs: ContextResponse(kwargs["context"]),
    )
    for index, owner in enumerate(owners):
        monkeypatch.setattr(routes, "get_current_user", lambda *args, owner=owner: owner)
        expected = {
            identity: states[index] if states[index] is not None else JobStatus.NEW
            for identity, states in combinations.items()
        }
        items = list_route(session).items
        actual_list = {str(item.id): item.status for item in items}
        if actual_list != expected:
            differences.append(f"owner{index}: list")
        actual_detail = {
            identity: routes.get_job(Request({"type": "http"}), uuid.UUID(identity), session).status
            for identity in combinations
        }
        if actual_detail != expected:
            differences.append(f"owner{index}: detail")
        response = routes.export_jobs(
            Request({"type": "http"}), session, min_score=None, profile="engineering", radar="all",
            include_disabled_sources=True,
        )
        assert response.status_code == 200
        reader = csv.DictReader(io.StringIO(captured["csv"].lstrip("\ufeff")))
        records = list(reader)
        assert len(reader.fieldnames or []) == 36
        assert len(records) == len(expected) == 49
        if {row["id"]: JobStatus(row["status"]) for row in records} != expected:
            differences.append(f"owner{index}: CSV")
        for status in JobStatus:
            wanted = {identity for identity, value in expected.items() if value == status}
            filtered = list_route(session, status)
            if {str(item.id) for item in filtered.items} != wanted:
                differences.append(f"owner{index}: filter {status.value}")
            if any(item.status != status for item in filtered.items):
                differences.append(f"owner{index}: filter display {status.value}")
        stats = routes.job_stats(
            Request({"type": "http"}), session, profile="engineering", radar="all",
        )
        counts = {status.value: count for status, count in Counter(expected.values()).items()}
        if stats.by_status != counts:
            differences.append(f"owner{index}: stats")
        assert stats.total == len(expected)
        page = routes.web_index(
            Request({"type": "http"}), session, min_score=None, match_level=None, technology=None,
            remote_type=None, status_filter=None, salary_known=False, q=None,
            profile="engineering", radar="all", category=None, verified_only=False,
            sort="score", order="desc",
        )
        assert isinstance(page, ContextResponse)
        if page.context["stats"]["by_status"] != counts:
            differences.append(f"owner{index}: web stats")
        shown = {
            str(job.id): page.context["user_statuses"].get(str(job.id), job.status)
            for job in page.context["jobs"]
        }
        if shown != expected:
            differences.append(f"owner{index}: web status context")
        personal = repository.get_user_statuses(session, owner.id, [])
        assert personal == {}
    assert state_snapshot(session) == before
    assert set(session.scalars(select(JobOffer.status))) == {shared}
    assert not differences, differences


@pytest.mark.parametrize("shared", list(JobStatus))
def test_reads_without_user_keep_shared_legacy_status(
    session: Session, monkeypatch: pytest.MonkeyPatch, shared: JobStatus,
) -> None:
    prepare(session, shared)
    monkeypatch.setattr(routes, "get_current_user", lambda *args: None)
    items = list_route(session).items
    assert len(items) == 49
    assert {item.status for item in items} == {shared}
    assert routes.get_job(Request({"type": "http"}), items[0].id, session).status == shared
    stats = routes.job_stats(Request({"type": "http"}), session, profile="engineering", radar="all")
    assert stats.by_status == {shared.value: 49}
    repository = JobRepository()
    for state in JobStatus:
        jobs = repository.list_jobs(session, JobFilters(status=state, user_id=None, limit=100))
        assert len(jobs) == (49 if state == shared else 0)


def test_updating_one_owner_preserves_the_other_owner_and_shared_state(
    session: Session,
) -> None:
    owners, combinations = prepare(session, JobStatus.REJECTED)
    identity = next(key for key, states in combinations.items() if states == (None, None))
    repository = JobRepository()
    before_other = [row for row in state_snapshot(session) if row.user_id == owners[1].id]
    offer = repository.update_user_status(
        session, user_id=owners[0].id, job_id=uuid.UUID(identity), status=JobStatus.APPLIED,
    )
    assert offer is not None
    session.commit()
    updated = repository.get_user_statuses(session, owners[0].id, [offer])
    assert updated[identity] == JobStatus.APPLIED
    assert repository.get_user_statuses(session, owners[1].id, [offer])[identity] == JobStatus.NEW
    assert offer.status == JobStatus.REJECTED
    assert [row for row in state_snapshot(session) if row.user_id == owners[1].id] == before_other
