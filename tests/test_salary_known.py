"""Published salary bounds and guaranteed minimums are separate filter contracts."""

from __future__ import annotations

import csv
import io
import uuid
from dataclasses import replace
from itertools import product
from typing import Any

import pytest
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from test_complete_export import export_app as export_app
from test_complete_export import seed

from app.api import routes
from app.formatting import salary_label
from app.models.enums import JobStatus
from app.models.job import JobOffer, UserJobState
from app.repositories.jobs import JobFilters, JobRepository
from app.scoring.salary import extract_salary
from app.security.auth import SESSION_COOKIE_NAME, create_session_token


@pytest.mark.parametrize(
    "unknown,minimum,maximum", list(product([False, True], [None, 0, 30000], [None, 0, 40000]))
)
def test_published_and_unknown_partition_supported_storage_states(
    export_app: Any, unknown: bool, minimum: int | None, maximum: int | None,
) -> None:
    _, engine = export_app
    identity = next(iter(seed(
        engine, 1, salary_unknown=unknown, salary_min=minimum, salary_max=maximum,
    )))
    repository = JobRepository()
    filters = JobFilters(profile_key="engineering", radar="current")
    with Session(engine) as session:
        published = {str(job.id) for job in repository.list_jobs(
            session, replace(filters, salary_known=True),
        )}
        unpublished = {str(job.id) for job in repository.list_jobs(
            session, replace(filters, salary_known=False),
        )}
    wanted = not unknown and (minimum is not None or maximum is not None)
    assert published == ({identity} if wanted else set())
    assert unpublished == (set() if wanted else {identity})
    assert published.isdisjoint(unpublished)
    assert published | unpublished == {identity}


def test_null_salary_flag_is_not_a_supported_persisted_state(export_app: Any) -> None:
    _, engine = export_app
    seed(engine, 1)
    with Session(engine) as session:
        offer = session.scalar(select(JobOffer))
        assert offer is not None
        offer.salary_unknown = None  # type: ignore[assignment]
        with pytest.raises(IntegrityError):
            session.flush()
        session.rollback()


def test_extracted_salary_ceiling_is_published_without_a_guaranteed_minimum(
    export_app: Any,
) -> None:
    _, engine = export_app
    salary = extract_salary("Salary up to 40000 EUR per year")
    assert salary.salary_min is None and salary.salary_max == 40000 and not salary.unknown
    assert salary_label(
        salary.salary_min, salary.salary_max, salary.currency, salary.unknown,
    ) == "up to 40,000 EUR"
    identity = next(iter(seed(
        engine, 1, salary_min=salary.salary_min, salary_max=salary.salary_max,
        salary_unknown=salary.unknown, salary_currency=salary.currency,
        salary_period=salary.period, salary_original_text=salary.original_text,
    )))
    repository = JobRepository()
    filters = JobFilters(salary_known=True)
    with Session(engine) as session:
        assert [str(job.id) for job in repository.list_jobs(session, filters)] == [identity]
        assert repository.list_jobs(session, replace(filters, salary_min=30000)) == []
        assert repository.list_jobs(session, replace(filters, salary_min=0)) == []


def test_authenticated_surfaces_preserve_filters_counts_and_owner_states(
    export_app: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    app, engine = export_app
    identities = sorted(seed(engine, 7))
    # Ceiling, minimum-only, range, single value, unpublished, zero ceiling, other profile.
    states = [
        (None, 40000, False), (30000, None, False), (30000, 40000, False),
        (35000, 35000, False), (None, None, True), (None, 0, False),
        (None, 45000, False),
    ]
    with Session(engine) as session:
        for identity, (minimum, maximum, unknown) in zip(identities, states, strict=True):
            offer = session.get(JobOffer, uuid.UUID(identity))
            assert offer is not None
            offer.salary_min, offer.salary_max, offer.salary_unknown = minimum, maximum, unknown
            offer.salary_currency = "EUR"
        other = session.get(JobOffer, uuid.UUID(identities[-1]))
        assert other is not None
        other.profile_key = "operations"
        session.add(UserJobState(
            user_id=1, job_offer_id=uuid.UUID(identities[0]), status=JobStatus.APPLIED,
        ))
        session.add(UserJobState(
            user_id=2, job_offer_id=uuid.UUID(identities[1]), status=JobStatus.INTERESTED,
        ))
        session.commit()
        before = list(session.execute(select(
            UserJobState.user_id, UserJobState.job_offer_id, UserJobState.status,
        ).order_by(UserJobState.user_id, UserJobState.job_offer_id)))

    # Capture backend dashboard context through real ASGI without rendering frontend files.
    def dashboard(**kwargs: Any) -> JSONResponse:
        context = kwargs["context"]
        return JSONResponse({
            "ids": [str(job.id) for job in context["jobs"]],
            "stats": context["stats"],
        })

    monkeypatch.setattr(routes.templates, "TemplateResponse", dashboard)
    published = set(identities[:4]) | {identities[5]}
    with TestClient(app) as client:
        for owner in (1, 2):
            client.cookies.set(SESSION_COOKIE_NAME, create_session_token(owner))
            query = "profile=engineering&radar=all&salary_known=true"
            response = client.get("/jobs?" + query)
            assert response.status_code == 200
            items = {item["id"]: item for item in response.json()["items"]}
            assert set(items) == published
            assert items[identities[0]]["salary_min"] is None
            assert items[identities[0]]["salary_max"] == 40000
            assert items[identities[0]]["status"] == ("applied" if owner == 1 else "new")
            page = client.get("/?" + query)
            assert page.status_code == 200
            assert set(page.json()["ids"]) == published
            assert page.json()["stats"]["total"] == 5
            assert sum(page.json()["stats"]["by_status"].values()) == 5
            combined = client.get("/jobs?" + query + "&salary_min=30000&remote_type=remote")
            assert combined.status_code == 200
            assert {item["id"] for item in combined.json()["items"]} == set(identities[1:4])
            status = "applied" if owner == 1 else "new"
            personal = client.get("/jobs?" + query + "&status=" + status)
            assert personal.status_code == 200
            assert {item["id"] for item in personal.json()["items"]} == (
                {identities[0]} if owner == 1 else published - {identities[1]}
            )
            # Existing API false means no published-salary restriction, not unknown-only.
            all_rows = client.get("/jobs?profile=engineering&radar=all&salary_known=false")
            assert len(all_rows.json()["items"]) == 6
            # Stats/export have no salary filter parameter; retain their existing scope.
            stats = client.get("/jobs/stats?profile=engineering&radar=all")
            assert stats.status_code == 200 and stats.json()["total"] == 6
            exported = client.get("/jobs/export?profile=engineering&radar=all")
            assert exported.status_code == 200
            reader = csv.DictReader(io.StringIO(exported.text.lstrip("\ufeff")))
            rows = {row["id"]: row for row in reader}
            assert len(reader.fieldnames or []) == 36 and set(rows) == set(identities[:6])
            assert rows[identities[0]]["salary/rate"] == "up to 40,000 EUR"
            assert rows[identities[0]]["status"] == ("applied" if owner == 1 else "new")
    with Session(engine) as session:
        assert list(session.execute(select(
            UserJobState.user_id, UserJobState.job_offer_id, UserJobState.status,
        ).order_by(UserJobState.user_id, UserJobState.job_offer_id))) == before
        assert {job.status for job in session.scalars(select(JobOffer))} == {JobStatus.REJECTED}
