"""Complete CSV exports through ASGI, using only synthetic database records."""

from __future__ import annotations

import asyncio
import csv
import io
import json
import os
import uuid
import weakref
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

import pytest
import yaml
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, insert, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api import routes
from app.core.config import clear_config_cache
from app.db.base import Base
from app.db.session import get_session
from app.models.enums import JobStatus, RemoteType
from app.models.job import Company, JobOffer, JobSource, User, UserJobState
from app.repositories.jobs import JobFilters, JobRepository
from app.security.auth import SESSION_COOKIE_NAME, create_session_token
from app.services import job_export


@compiles(JSONB, "sqlite")
def sqlite_json(type_: Any, compiler: Any, **kw: Any) -> str:
    return "JSON"


@pytest.fixture()
def export_app(tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> Iterator[Any]:
    config = tmp_path / "config"
    config.mkdir()
    definitions = {
        "default_profile_key": "engineering",
        "profiles": {
            "engineering": {"profile_config": "profile.yml"},
            "operations": {"profile_config": "profile.yml"},
        },
    }
    (config / "profiles.yml").write_text(yaml.safe_dump(definitions), encoding="utf-8")
    (config / "profile.yml").write_text("profile:\n  career: {enabled: true}\n", encoding="utf-8")
    monkeypatch.setenv("CONFIG_DIR", str(config))
    clear_config_cache()
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add_all(
            [
                User(
                    id=i,
                    email=f"owner{i}@example.invalid",
                    display_name=f"Owner {i}",
                    password_hash="synthetic",
                )
                for i in (1, 2)
            ]
        )
        session.add_all(
            [
                Company(id=1, name='Synthetic, "company"'),
                JobSource(id=1, name="enabled", enabled=True, profile_key="engineering"),
                JobSource(id=2, name="disabled", enabled=False, profile_key="engineering"),
            ]
        )
        session.commit()
    app = FastAPI()
    app.include_router(routes.router)
    app.state.request_sessions = []

    def dependency() -> Iterator[Session]:
        with Session(engine) as session:
            app.state.request_sessions.append(session)
            yield session

    app.dependency_overrides[get_session] = dependency
    try:
        yield app, engine
    finally:
        engine.dispose()
        clear_config_cache()


def seed(engine: Any, count: int, **overrides: Any) -> set[str]:
    now = datetime(2026, 10, 24, 12, tzinfo=UTC)
    rows = [
        dict(
            id=uuid.UUID(int=(0xAB << 120) + i + 1),
            source_id=1,
            company_id=1,
            source_job_id=str(i),
            profile_key="engineering",
            title=f"Synthetic {i}",
            normalized_title=f"synthetic {i}",
            description='Comas, "comillas"\nUnicode: ñ ☕',
            requirements='SQL, Java\n"Spring"',
            url=f"https://example.invalid/jobs/{i}",
            remote_type=RemoteType.REMOTE,
            technologies=["java"],
            raw_payload={},
            match_reasons={"assessment": {"radar": "current", "recommendation": "B"}},
            negative_reasons={},
            content_hash=f"{i:064x}",
            match_score=70,
            match_level="good",
            salary_unknown=True,
            status=JobStatus.REJECTED,
            first_seen_at=now,
            last_seen_at=now,
            created_at=now,
            updated_at=now,
            publication_date=now,
        )
        for i in range(count)
    ]
    for row in rows:
        row.update(overrides)
    with Session(engine) as session:
        if rows:
            session.execute(insert(JobOffer), rows)
        session.commit()
    return {str(row["id"]) for row in rows}


@pytest.mark.parametrize("count", [0, 9999, 10000, 10001])
def test_export_returns_every_matching_id_once_over_asgi(export_app: Any, count: int) -> None:
    app, engine = export_app
    expected = seed(engine, count)
    with TestClient(app) as client:
        client.cookies.set(SESSION_COOKIE_NAME, create_session_token(1))
        response = client.get("/jobs/export?profile=engineering&radar=all")
    assert response.status_code == 200
    assert response.text.startswith("\ufeff")
    reader = csv.DictReader(io.StringIO(response.text.lstrip("\ufeff")))
    rows = list(reader)
    assert len(reader.fieldnames or []) == 36
    assert len(rows) == count
    assert {row["id"] for row in rows} == expected
    assert len({row["id"] for row in rows}) == len(rows)
    assert [row["id"] for row in rows] == sorted(expected)
    if rows:
        assert rows[0]["description"] == 'Comas, "comillas"\nUnicode: ñ ☕'
        assert rows[0]["requirements"] == 'SQL, Java\n"Spring"'
        assert {row["status"] for row in rows} == {"new"}


def read_csv(response: Any) -> dict[str, dict[str, str]]:
    assert response.status_code == 200
    return {row["id"]: row for row in csv.DictReader(io.StringIO(response.text.lstrip("\ufeff")))}


def test_export_preserves_filters_source_option_and_personal_owners(export_app: Any) -> None:
    app, engine = export_app
    identities = sorted(seed(engine, 5))
    with Session(engine) as session:
        offers: list[JobOffer] = []
        for identity in identities:
            offer = session.get(JobOffer, uuid.UUID(identity))
            assert offer is not None
            offers.append(offer)
        offers[1].source_id = 2
        offers[2].profile_key = "operations"
        offers[3].match_score = 10
        offers[4].match_reasons = {"assessment": {"radar": "strategic"}}
        session.add_all(
            [
                UserJobState(user_id=1, job_offer_id=offers[0].id, status=JobStatus.APPLIED),
                UserJobState(user_id=2, job_offer_id=offers[0].id, status=JobStatus.INTERESTED),
            ]
        )
        session.commit()
        before = list(session.execute(select(UserJobState.user_id, UserJobState.status)))
    cases = [
        ("profile=engineering", {identities[0], identities[3]}),
        ("profile=engineering&min_score=50", {identities[0]}),
        ("profile=engineering&radar=all", {identities[0], identities[3], identities[4]}),
        (
            "profile=engineering&include_disabled_sources=true&min_score=50",
            {identities[0], identities[1]},
        ),
        ("profile=operations&radar=all", {identities[2]}),
    ]
    with TestClient(app) as client:
        assert client.get("/jobs/export").status_code == 401
        for owner, status in [(1, "applied"), (2, "interested")]:
            client.cookies.set(SESSION_COOKIE_NAME, create_session_token(owner))
            for query, wanted in cases:
                records = read_csv(client.get("/jobs/export?" + query))
                assert set(records) == wanted
                if identities[0] in records:
                    assert records[identities[0]]["status"] == status
                assert all(
                    row["status"] == "new" for key, row in records.items() if key != identities[0]
                )
    with Session(engine) as session:
        assert list(session.execute(select(UserJobState.user_id, UserJobState.status))) == before


def track_stream(
    app: FastAPI,
    monkeypatch: pytest.MonkeyPatch,
) -> dict[str, Any]:
    metrics: dict[str, Any] = {
        "sessions": [],
        "results": [],
        "closed_sessions": 0,
        "peak_live_offers": 0,
        "max_batch_rows": 0,
        "max_status_keys": 0,
        "offer_queries": 0,
        "forced_request_session_close": False,
    }
    live: weakref.WeakSet[JobOffer] = weakref.WeakSet()

    class StreamSession(Session):
        def __enter__(self) -> Any:
            # Prove the stream can consume after request-session closure.
            for request_session in app.state.request_sessions:
                request_session.close()
            metrics["forced_request_session_close"] = bool(app.state.request_sessions)
            metrics["sessions"].append(self)
            return super().__enter__()

        def scalars(self, *args: Any, **kwargs: Any) -> Any:
            result = super().scalars(*args, **kwargs)
            metrics["offer_queries"] += 1
            metrics["results"].append(result)
            return result

        def close(self) -> None:
            metrics["closed_sessions"] += 1
            super().close()

    @event.listens_for(StreamSession, "loaded_as_persistent")
    def loaded(session: Session, instance: Any) -> None:
        if isinstance(instance, JobOffer):
            live.add(instance)
            metrics["peak_live_offers"] = max(metrics["peak_live_offers"], len(live))

    original = JobRepository.get_user_statuses

    def statuses(self: Any, session: Session, user_id: int, jobs: Any) -> Any:
        values = original(self, session, user_id, jobs)
        metrics["max_batch_rows"] = max(metrics["max_batch_rows"], len(jobs))
        metrics["max_status_keys"] = max(metrics["max_status_keys"], len(values))
        return values

    monkeypatch.setattr(routes, "Session", StreamSession)
    monkeypatch.setattr(JobRepository, "get_user_statuses", statuses)
    return metrics


def assert_closed(metrics: dict[str, Any]) -> None:
    assert len(metrics["sessions"]) == metrics["closed_sessions"] == 1
    assert all(result.closed for result in metrics["results"])
    assert all(not session.identity_map for session in metrics["sessions"])


def test_export_bounds_server_rows_states_and_owns_its_session(
    export_app: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app, engine = export_app
    expected = seed(engine, 10001)
    metrics = track_stream(app, monkeypatch)
    with TestClient(app) as client:
        client.cookies.set(SESSION_COOKIE_NAME, create_session_token(1))
        records = read_csv(client.get("/jobs/export?radar=all"))
    assert set(records) == expected
    assert metrics["offer_queries"] == 1
    assert metrics["max_batch_rows"] == metrics["max_status_keys"] == 500
    assert metrics["peak_live_offers"] <= 1000
    assert metrics["forced_request_session_close"]
    assert_closed(metrics)
    printable = {k: v for k, v in metrics.items() if k not in {"sessions", "results"}}
    print("EXPORT_METRICS=" + json.dumps(printable))


def test_export_closes_cursor_and_session_on_serialization_failure(
    export_app: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app, engine = export_app
    seed(engine, 1001)
    metrics = track_stream(app, monkeypatch)
    calls = 0
    original = job_export.salary_label

    def fail(*args: Any, **kwargs: Any) -> str:
        nonlocal calls
        calls += 1
        if calls == 501:
            raise RuntimeError("synthetic serialization failure")
        return original(*args, **kwargs)

    monkeypatch.setattr(job_export, "salary_label", fail)
    with TestClient(app) as client:
        client.cookies.set(SESSION_COOKIE_NAME, create_session_token(1))
        with pytest.raises(RuntimeError, match="synthetic serialization failure"):
            client.get("/jobs/export?radar=all")
    assert_closed(metrics)


@pytest.mark.parametrize("exit_mode", ["disconnect", "send_failure", "task_cancel"])
def test_asgi_stream_closes_on_disconnect_send_error_or_cancellation(
    export_app: Any,
    monkeypatch: pytest.MonkeyPatch,
    exit_mode: str,
) -> None:
    app, engine = export_app
    seed(engine, 1001)
    metrics = track_stream(app, monkeypatch)

    async def run() -> None:
        disconnected = asyncio.Event()
        first = True

        async def receive() -> Any:
            nonlocal first
            if first:
                first = False
                return {"type": "http.request", "body": b"", "more_body": False}
            await disconnected.wait()
            return {"type": "http.disconnect"}

        async def send(message: Any) -> None:
            body = message.get("body", b"")
            if body and not body.startswith(b"\xef\xbb\xbf"):
                if exit_mode == "send_failure":
                    raise OSError("synthetic client write failure")
                if exit_mode == "task_cancel":
                    task = asyncio.current_task()
                    assert task is not None
                    task.cancel()
                    await asyncio.sleep(0)
                disconnected.set()
                await asyncio.Event().wait()

        cookie = f"{SESSION_COOKIE_NAME}={create_session_token(1)}".encode()
        scope = {
            "type": "http",
            "asgi": {
                "version": "3.0",
                "spec_version": "2.0" if exit_mode == "disconnect" else "2.4",
            },
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": "/jobs/export",
            "raw_path": b"/jobs/export",
            "root_path": "",
            "query_string": b"radar=all",
            "headers": [(b"cookie", cookie)],
            "server": ("testserver", 80),
            "client": ("testclient", 123),
        }
        try:
            await asyncio.wait_for(app(scope, receive, send), timeout=3)
        except asyncio.CancelledError:
            assert exit_mode == "task_cancel"
        except Exception as error:
            assert exit_mode == "send_failure"
            assert type(error).__name__ == "ClientDisconnect"

    asyncio.run(run())
    assert metrics["offer_queries"] == 1
    assert_closed(metrics)


@pytest.mark.integration
def test_postgresql_export_uses_named_cursor_and_closes_it() -> None:
    url = os.getenv("JOBRADAR_EXPORT_TEST_POSTGRES_URL")
    if not url:
        pytest.skip("Set JOBRADAR_EXPORT_TEST_POSTGRES_URL to a dedicated PostgreSQL test database")
    engine = create_engine(url)
    cursors = []

    @event.listens_for(engine, "after_cursor_execute")
    def cursor_used(
        conn: Any, cursor: Any, statement: Any, params: Any, context: Any, many: Any
    ) -> None:
        if context.execution_options.get("yield_per"):
            cursors.append(cursor)

    try:
        with engine.connect() as connection, connection.begin() as transaction:
            Base.metadata.create_all(connection)
            with Session(bind=connection) as session:
                suffix = uuid.uuid4().hex
                source = JobSource(name="export-test-" + suffix, enabled=True, profile_key=suffix)
                company = Company(name="export-test-" + suffix)
                session.add_all([source, company])
                session.flush()
                for index in range(1001):
                    session.add(
                        JobOffer(
                            source=source,
                            company=company,
                            profile_key=suffix,
                            source_job_id=str(index),
                            title="Synthetic",
                            normalized_title="synthetic",
                            description="Synthetic export integration",
                            content_hash=str(index),
                        )
                    )
                session.flush()
                batches = JobRepository().iter_job_batches(
                    session,
                    JobFilters(profile_key=suffix),
                    batch_size=500,
                )
                identifiers: set[uuid.UUID] = set()
                for batch in batches:
                    assert len(batch) <= 500
                    identifiers.update(row.id for row in batch)
                assert len(identifiers) == 1001
                assert len(cursors) == 1 and cursors[0].name
                assert cursors[0].closed
            transaction.rollback()
    finally:
        engine.dispose()
