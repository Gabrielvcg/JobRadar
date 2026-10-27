"""Static pagination stays stable across two real SQLite access plans."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import create_engine, event, insert, select, text
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models.job import Company, JobOffer, JobSource
from app.repositories.jobs import JobFilters, JobRepository


@compiles(JSONB, "sqlite")
def sqlite_json(type_: Any, compiler: Any, **kw: Any) -> str:
    return "JSON"


@pytest.fixture()
def session() -> Iterator[Session]:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as value:
        # Leave one eligible profile access index at a time in this synthetic fixture.
        value.execute(text("DROP INDEX ix_job_offers_profile_key"))
        value.add_all(
            [
                Company(id=1, name="Synthetic"),
                JobSource(id=1, name="synthetic", enabled=True, profile_key="target"),
            ]
        )
        value.flush()
        now = datetime(2026, 10, 24, 12, tzinfo=UTC)
        rows = [
            dict(
                id=uuid.UUID(int=(0xAB << 120) + i + 1),
                source_id=1,
                company_id=1,
                profile_key="target" if i < 24 else f"other{i % 10}",
                source_job_id=str(i),
                title="Synthetic",
                normalized_title="synthetic",
                description="Offline fixture",
                content_hash=str(i),
                match_score=70,
                match_level="good",
                match_reasons={"assessment": {"recommendation": "B"}},
                publication_date=now,
                created_at=now,
            )
            for i in range(1024)
        ]
        value.execute(insert(JobOffer), rows)
        value.commit()
        yield value
    engine.dispose()


def access_plan(session: Session, direction: str) -> None:
    assert direction in {"ASC", "DESC"}
    session.execute(text("DROP INDEX IF EXISTS ix_pagination_probe"))
    session.execute(
        text(f"CREATE INDEX ix_pagination_probe ON job_offers (profile_key, id {direction})")
    )
    session.commit()


@pytest.mark.parametrize(
    "sort,order,null_date",
    [
        ("score", "asc", False),
        ("score", "desc", False),
        ("date", "asc", False),
        ("date", "desc", False),
        ("date", "asc", True),
        ("date", "desc", True),
        ("id", "asc", False),
        ("id", "desc", False),
    ],
)
def test_tied_pages_stay_identical_across_real_access_plans(
    session: Session,
    sort: str,
    order: str,
    null_date: bool,
) -> None:
    repository = JobRepository()
    if null_date:
        session.execute(text("UPDATE job_offers SET publication_date = NULL"))
        session.commit()
    filters = JobFilters(profile_key="target", sort=sort, order=order, limit=5)
    query = repository._apply_sort(repository._filtered_statement(filters), filters)
    sql = str(
        query.limit(5).compile(
            dialect=session.get_bind().dialect,
            compile_kwargs={"literal_binds": True},
        )
    )
    all_ids = sorted(session.scalars(select(JobOffer.id).where(JobOffer.profile_key == "target")))
    snapshots = []
    for direction in ("ASC", "DESC"):
        access_plan(session, direction)
        plan = list(session.execute(text("EXPLAIN QUERY PLAN " + sql)))
        assert any("USING INDEX ix_pagination_probe" in row[3] for row in plan)
        pages = [
            [job.id for job in repository.list_jobs(session, replace(filters, offset=offset))]
            for offset in range(0, 25, 5)
        ]
        snapshots.append(pages)
    # Deliberately change only the available index between page requests.
    mixed: list[uuid.UUID] = []
    for index, offset in enumerate(range(0, 25, 5)):
        access_plan(session, "ASC" if index % 2 == 0 else "DESC")
        mixed.extend(
            job.id for job in repository.list_jobs(session, replace(filters, offset=offset))
        )
    assert snapshots[0] == snapshots[1]
    assert [identity for page in snapshots[0] for identity in page] == all_ids
    assert mixed == all_ids
    assert len(mixed) == len(set(mixed)) == 24


def test_primary_sort_priorities_remain_before_id(session: Session) -> None:
    repository = JobRepository()
    offers = repository.list_jobs(session, JobFilters(profile_key="target", sort="id", limit=7))
    now = datetime(2026, 10, 24, 12, tzinfo=UTC)
    advice = ["D", "C", "U", "B", "A", "A", "A"]
    for job, recommendation in zip(offers, advice, strict=True):
        job.match_reasons = {"assessment": {"recommendation": recommendation}}
        job.match_score = 70
        job.created_at = now
        job.publication_date = now
    offers[5].created_at = now + timedelta(seconds=1)
    offers[6].match_score = 90
    session.commit()
    filters = JobFilters(profile_key="target", limit=24)
    desc = repository.list_jobs(session, filters)
    assert desc[:3] == [offers[6], offers[5], offers[4]]
    assert (
        desc.index(offers[3])
        < desc.index(offers[2])
        < desc.index(offers[1])
        < desc.index(offers[0])
    )
    asc = repository.list_jobs(session, replace(filters, order="asc"))
    assert asc[0] == offers[5]  # Ascending score intentionally has no advice priority.
    assert asc[-1] == offers[6]
    offers[0].publication_date = None
    offers[1].publication_date = now - timedelta(days=1)
    offers[2].publication_date = now + timedelta(days=1)
    session.commit()
    for order, first in (("asc", offers[1]), ("desc", offers[2])):
        date = repository.list_jobs(session, replace(filters, sort="date", order=order))
        assert date[0] == first and date[-1] == offers[0]
        assert date.index(offers[5]) < date.index(offers[4])


@pytest.mark.parametrize(
    "sort,order",
    [
        ("score", "asc"),
        ("score", "desc"),
        ("date", "asc"),
        ("date", "desc"),
        ("id", "desc"),
    ],
)
def test_postgresql_sort_compilation_and_export_use_one_final_id(
    session: Session,
    sort: str,
    order: str,
) -> None:
    repository = JobRepository()
    filters = JobFilters(profile_key="target", sort=sort, order=order)
    statement = repository._apply_sort(repository._filtered_statement(filters), filters)
    sql = str(
        statement.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True})
    )
    order_sql = sql.split("ORDER BY ", 1)[1]
    assert order_sql.rstrip().endswith("job_offers.id")
    assert order_sql.count("job_offers.id") == 1
    assert "NULLS LAST" in order_sql or sort == "id"
    export_queries: list[str] = []

    def capture_query(
        connection: Any,
        cursor: Any,
        sql: str,
        parameters: Any,
        context: Any,
        many: bool,
    ) -> None:
        if context.execution_options.get("yield_per"):
            export_queries.append(sql)

    bind = session.get_bind()
    event.listen(bind, "before_cursor_execute", capture_query)
    batches = repository.iter_job_batches(session, filters, batch_size=5)
    try:
        exported = [job.id for batch in batches for job in batch]
    finally:
        batches.close()
        event.remove(bind, "before_cursor_execute", capture_query)
    assert len(export_queries) == 1
    assert export_queries[0].split("ORDER BY ", 1)[1].count("job_offers.id") == 1
    assert exported == [job.id for job in repository.list_jobs(session, replace(filters, limit=24))]
