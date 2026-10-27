"""Budgeted verification selection scans bounded batches before any rescoring writes."""

from __future__ import annotations

import asyncio
import weakref
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlsplit

import pytest
from sqlalchemy import event, select
from sqlalchemy.orm import Session
from test_complete_export import export_app as export_app
from test_complete_export import seed

from app.core.availability import VERIFICATION_KEY, current_verification
from app.models.job import JobOffer
from app.repositories.jobs import JobFilters, JobRepository
from app.scoring.engine import ScoreResult
from app.services import verification


def bind_proof(offer: JobOffer, state: str, hours: int = 0) -> dict[str, Any]:
    return {
        "state": state, "listing_url": offer.url,
        "checked_at": (datetime.now(UTC) - timedelta(hours=hours)).isoformat(),
    }


@pytest.fixture()
def boundary(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    calls: dict[str, Any] = {"urls": [], "scores": [], "engines": [], "slept": []}

    class Engine:
        def __init__(self, key: str) -> None:
            calls["engines"].append(key)

        def score(self, job: Any) -> ScoreResult:
            calls["scores"].append(job.url)
            return ScoreResult(
                score=calls.get("new_score", 99), level="good", positive=[], negative=[],
                assessment={"radar": "current"},
            )

    async def check(client: Any, url: str, title: str) -> dict[str, Any]:
        if "assert_before_check" in calls:
            calls["assert_before_check"]()
        calls["urls"].append(url)
        return {
            "state": calls.get("state", "active"), "listing_url": url,
            "checked_at": datetime.now(UTC).isoformat(),
        }

    async def sleep(delay: float) -> None:
        calls["slept"].append(delay)

    monkeypatch.setattr(verification, "ScoringEngine", Engine)
    monkeypatch.setattr(verification, "verify_listing", check)
    monkeypatch.setattr(verification.asyncio, "sleep", sleep)
    return calls


@pytest.mark.parametrize("fresh_count", [499, 500, 501, 1500])
def test_pending_beyond_fresh_batches_is_reached(
    export_app: Any, boundary: dict[str, Any], fresh_count: int,
) -> None:
    _, engine = export_app
    seed(engine, fresh_count + 1)
    with Session(engine) as session:
        offers = list(session.scalars(select(JobOffer).order_by(JobOffer.id)))
        for offer in offers[:-1]:
            offer.raw_payload = {VERIFICATION_KEY: bind_proof(offer, "active")}
        target = offers[-1]
        target.match_score = 35
        session.commit()
        result = asyncio.run(verification.OfferVerificationService().run(session, limit=2))
        assert result["checked"] == 1 and boundary["urls"] == [target.url]
        assert boundary["scores"] == boundary["urls"]


@pytest.mark.parametrize("raw", [None, [], "damaged", 42, {}, {"state": "unverified"}])
def test_non_dictionary_proof_does_not_abort_scheduling(
    export_app: Any, boundary: dict[str, Any], raw: Any,
) -> None:
    _, engine = export_app
    seed(engine, 2)
    with Session(engine) as session:
        offers = list(session.scalars(select(JobOffer).order_by(JobOffer.id)))
        offers[0].raw_payload = {VERIFICATION_KEY: raw}
        session.commit()
        assert current_verification(offers[0].raw_payload, offers[0].url)["state"] == "unverified"
        result = asyncio.run(verification.OfferVerificationService().run(session, limit=2))
        assert result["checked"] == 2
        assert len(set(boundary["urls"])) == 2


def test_global_priority_matches_complete_stable_sort_not_id_or_query_order(
    export_app: Any, boundary: dict[str, Any],
) -> None:
    _, engine = export_app
    seed(engine, 1003)
    with Session(engine) as session:
        offers = list(session.scalars(select(JobOffer).order_by(JobOffer.id)))
        for index, offer in enumerate(offers):
            offer.url = f"https://himalayas.app/jobs/{index}"
            offer.match_score = 80
        # Lower-score trusted hosts outrank every portal, older cache beats newer,
        # and equal pending keys retain the repository's advice/creation/ID order.
        for index, score, age in [(999, 35, 48), (1000, 50, 72), (1001, 50, 72)]:
            offer = offers[index]
            offer.url = f"https://jobs.lever.co/example/{index}"
            offer.match_score = score
            offer.raw_payload = {VERIFICATION_KEY: bind_proof(offer, "unverified", age)}
        # Make the two same-age values exact, so recommendation breaks the tie.
        offers[1001].raw_payload = {
            VERIFICATION_KEY: {**offers[1000].raw_payload[VERIFICATION_KEY],
                               "listing_url": offers[1001].url},
        }
        offers[1000].match_reasons = {"assessment": {"radar": "current", "recommendation": "A"}}
        offers[1001].match_reasons = {"assessment": {"radar": "current", "recommendation": "D"}}
        session.commit()
        candidates = JobRepository().list_jobs(
            session, JobFilters(
                profile_key="engineering", radar="current", min_score=35, limit=2000,
            ),
        )
        expected = sorted(candidates, key=lambda offer: (
            urlsplit(offer.url or "").hostname
            in {"himalayas.app", "remotive.com", "weworkremotely.com"},
            str(offer.raw_payload.get(VERIFICATION_KEY, {}).get("checked_at", "")),
            -offer.match_score,
        ))[:3]
        wanted = [offer.url for offer in expected]
        assert wanted == [offers[1000].url, offers[1001].url, offers[999].url]
        assert wanted != [offer.url for offer in candidates[:3]]
        boundary["new_score"] = 0  # Writes reorder/remove checked rows from eligibility.
        result = asyncio.run(verification.OfferVerificationService().run(session, limit=3))
        assert result["checked"] == 3 and boundary["urls"] == wanted
        assert len(set(boundary["urls"])) == 3


@pytest.mark.parametrize("limit", [0, -1])
def test_nonpositive_limit_avoids_queries_clients_and_scoring(
    export_app: Any, boundary: dict[str, Any], monkeypatch: pytest.MonkeyPatch, limit: int,
) -> None:
    _, engine = export_app
    seed(engine, 1)

    def unexpected(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("No HTTP client or query needed for exhausted budget")

    monkeypatch.setattr(verification.httpx, "AsyncClient", unexpected)
    with Session(engine) as session:
        monkeypatch.setattr(session, "scalars", unexpected)
        result = asyncio.run(verification.OfferVerificationService().run(session, limit=limit))
    assert result["checked"] == 0 and not boundary["urls"] and not boundary["engines"]


def test_profiles_share_budget_and_stop_before_unneeded_profile_scan(
    export_app: Any, boundary: dict[str, Any],
) -> None:
    _, engine = export_app
    seed(engine, 6)
    with Session(engine) as session:
        offers = list(session.scalars(select(JobOffer).order_by(JobOffer.id)))
        for offer in offers[3:]:
            offer.profile_key = "operations"
        session.commit()
        result = asyncio.run(verification.OfferVerificationService().run(session, limit=4))
        assert result["checked"] == 4
        assert boundary["urls"] == [offer.url for offer in offers[:4]]
        assert boundary["engines"] == ["engineering", "operations"]
    boundary["urls"].clear()
    boundary["engines"].clear()
    with Session(engine) as session:
        result = asyncio.run(verification.OfferVerificationService().run(
            session, limit=2, force=True,
        ))
    assert result["checked"] == 2 and boundary["engines"] == ["engineering"]


def test_failed_check_cache_force_and_exhaustion(
    export_app: Any, boundary: dict[str, Any],
) -> None:
    _, engine = export_app
    seed(engine, 3)
    boundary["state"] = "unverified"
    with Session(engine) as session:
        first = asyncio.run(verification.OfferVerificationService().run(session, limit=20))
        second = asyncio.run(verification.OfferVerificationService().run(session, limit=20))
        forced = asyncio.run(verification.OfferVerificationService().run(
            session, limit=1, force=True, profile_key="engineering",
        ))
    assert first["checked"] == first["unverified"] == 3
    assert second["checked"] == 0 and forced["checked"] == 1
    assert len(boundary["urls"]) == 4 and len(boundary["slept"]) == 4


def test_empty_candidates_do_not_construct_scoring_engine(
    export_app: Any, boundary: dict[str, Any],
) -> None:
    _, engine = export_app
    with Session(engine) as session:
        result = asyncio.run(verification.OfferVerificationService().run(session))
    assert result["checked"] == 0 and not boundary["engines"]


def test_bounded_retention_and_cursor_closed_before_check(
    export_app: Any, boundary: dict[str, Any], monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, engine = export_app
    seed(engine, 2501)
    live: weakref.WeakSet[JobOffer] = weakref.WeakSet()
    metrics = {"peak": 0, "rows": 0, "max_batch": 0, "queries": 0}
    results = []
    original_scalars = Session.scalars
    original_batches = JobRepository.iter_job_batches

    def scalars(self: Session, *args: Any, **kwargs: Any) -> Any:
        result = original_scalars(self, *args, **kwargs)
        results.append(result)
        metrics["queries"] += 1
        return result

    def batches(self: Any, *args: Any, **kwargs: Any) -> Any:
        source = original_batches(self, *args, **kwargs)
        try:
            for batch in source:
                metrics["rows"] += len(batch)
                metrics["max_batch"] = max(metrics["max_batch"], len(batch))
                yield batch
        finally:
            source.close()

    def loaded(session: Session, instance: Any) -> None:
        if isinstance(instance, JobOffer):
            live.add(instance)
            metrics["peak"] = max(metrics["peak"], len(live))

    def closed() -> None:
        assert results and all(result.closed for result in results)

    monkeypatch.setattr(Session, "scalars", scalars)
    monkeypatch.setattr(JobRepository, "iter_job_batches", batches)
    boundary["assert_before_check"] = closed
    event.listen(Session, "loaded_as_persistent", loaded)
    try:
        with Session(engine) as session:
            result = asyncio.run(verification.OfferVerificationService().run(
                session, limit=4, profile_key="engineering",
            ))
        assert result["checked"] == 4 and metrics["rows"] == 2501
        assert metrics["queries"] == 1
        assert metrics["max_batch"] <= 500 and metrics["peak"] <= 1005
        assert len(set(boundary["urls"])) == 4
        print("SCHEDULER_METRICS=" + str(metrics))
    finally:
        event.remove(Session, "loaded_as_persistent", loaded)

def test_existing_small_domain_priority_is_preserved(
    export_app: Any, boundary: dict[str, Any],
) -> None:
    _, engine = export_app
    seed(engine, 7)
    with Session(engine) as session:
        offers = list(session.scalars(select(JobOffer).order_by(JobOffer.id)))
        # Deliberately interleave host, timestamp, score and recommendation priorities.
        for index, offer in enumerate(offers):
            offer.match_score = [95, 35, 60, 60, 80, 45, 50][index]
            host = "himalayas.app" if index in {0, 4} else "jobs.lever.co"
            offer.url = f"https://{host}/example/{index}"
            if index in {2, 3}:
                offer.raw_payload = {VERIFICATION_KEY: bind_proof(offer, "unverified", 48)}
        offers[3].raw_payload = {VERIFICATION_KEY: {
            **offers[2].raw_payload[VERIFICATION_KEY], "listing_url": offers[3].url,
        }}
        offers[2].match_reasons = {"assessment": {"radar": "current", "recommendation": "D"}}
        offers[3].match_reasons = {"assessment": {"radar": "current", "recommendation": "A"}}
        session.commit()
        candidates = JobRepository().list_jobs(
            session, JobFilters(
                profile_key="engineering", radar="current", min_score=35, limit=500,
            ),
        )
        oracle = sorted(candidates, key=lambda offer: (
            urlsplit(offer.url or "").hostname
            in {"himalayas.app", "remotive.com", "weworkremotely.com"},
            str(offer.raw_payload.get(VERIFICATION_KEY, {}).get("checked_at", "")),
            -offer.match_score,
        ))
        expected = [offer.url for offer in oracle]
        assert expected != [offer.url for offer in candidates]
        assert expected.index(offers[3].url) < expected.index(offers[2].url)
        result = asyncio.run(verification.OfferVerificationService().run(session, limit=20))
        assert result["checked"] == 7 and boundary["urls"] == expected
