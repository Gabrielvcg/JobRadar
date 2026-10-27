"""Malformed raw proof must not break availability consumers."""

from __future__ import annotations

import copy
import csv
import io
import json
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Self

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from test_complete_export import assert_closed, seed, track_stream
from test_complete_export import export_app as export_app

from app.core import availability
from app.core.availability import VERIFICATION_KEY, current_verification
from app.repositories.jobs import JobRepository
from app.schemas.jobs import job_offer_to_read
from app.security.auth import SESSION_COOKIE_NAME, create_session_token

NOW = datetime(2026, 10, 24, 12, 0, 0, 123456, tzinfo=UTC)
URL = "https://example.invalid/jobs/java"
MISSING = object()
INVALID_JSON = [False, True, 0, 42, 1.5, [], ["active"], {}, {"value": URL}]


def proof(**changes: Any) -> dict[str, Any]:
    value = {
        "state": "active",
        "listing_url": URL,
        "checked_at": NOW.isoformat(),
        "application_url": URL + "/apply",
    }
    value.update(changes)
    for name in list(value):
        if value[name] is MISSING:
            del value[name]
    return {VERIFICATION_KEY: value}


@pytest.mark.parametrize("field", ["listing_url", "application_url", "state"])
@pytest.mark.parametrize("value", INVALID_JSON)
@pytest.mark.parametrize("age", [timedelta(0), timedelta(days=2), -timedelta(seconds=1)])
def test_nontext_consumed_metadata_is_always_unverified(
    field: str,
    value: Any,
    age: timedelta,
) -> None:
    payload = proof(**{field: value}, checked_at=(NOW - age).isoformat())
    original = copy.deepcopy(payload)
    result = current_verification(payload, URL, NOW)
    assert result["state"] == "unverified"
    assert result.get("application_url") is None
    assert payload == original


@pytest.mark.parametrize("value", [MISSING, None])
@pytest.mark.parametrize("age", [timedelta(0), timedelta(days=2), -timedelta(seconds=1)])
def test_missing_or_null_state_never_escapes_as_nontext(value: Any, age: timedelta) -> None:
    result = current_verification(
        proof(state=value, checked_at=(NOW - age).isoformat()),
        URL,
        NOW,
    )
    assert result["state"] == "unverified"


@pytest.mark.parametrize("field", ["listing_url", "application_url"])
@pytest.mark.parametrize("value", ["https://[bad", "https://example.invalid/?q=\ud800"])
def test_unparseable_proof_url_is_unverified(field: str, value: str) -> None:
    result = current_verification(proof(**{field: value}), URL, NOW)
    assert result["state"] == "unverified"
    assert result.get("application_url") is None


@pytest.mark.parametrize("value", [42, [], {"url": URL}, "https://[bad"])
def test_reader_does_not_raise_for_invalid_offer_url_argument(value: Any) -> None:
    # A malformed offer model can still violate DTO.url; that is outside this proof contract.
    assert current_verification(proof(), value, NOW)["state"] == "unverified"


@pytest.mark.parametrize("value", [MISSING, None, "", "   ", "/apply", "apply/now", URL])
def test_compatible_optional_application_url_has_no_new_scheme_policy(value: Any) -> None:
    result = current_verification(proof(application_url=value), URL, NOW)
    assert result["state"] == "active"
    if value is MISSING:
        assert "application_url" not in result
    else:
        assert result["application_url"] == value


@pytest.mark.parametrize(
    "state", ["closed", "listing_only", "unverified", "historical_custom", "", " "]
)
def test_textual_states_and_unused_extras_are_preserved(state: str) -> None:
    payload = proof(
        state=state,
        application_url={"unused": True},
        reason=["opaque"],
        evidence_level={"not_consumed_by_typed_field": True},
        extra=[1, 2],
    )
    assert current_verification(payload, URL, NOW) == payload[VERIFICATION_KEY]


@pytest.mark.parametrize("listing", [MISSING, None, "", "   "])
def test_existing_empty_url_binding_behavior_is_not_redefined(listing: Any) -> None:
    assert current_verification(proof(listing_url=listing), None, NOW)["state"] == "active"


@pytest.mark.parametrize("raw", [None, False, 42, "active", [], ["active"]])
def test_non_object_proof_is_unverified(raw: Any) -> None:
    assert current_verification({VERIFICATION_KEY: raw}, URL, NOW)["state"] == "unverified"


CASES = json.loads(
    (Path(__file__).parent / "fixtures/availability-r04-compatible.json").read_text()
)


@pytest.mark.parametrize("case", CASES, ids=[v["case"] for v in CASES])
def test_r04_compatible_availability_is_preserved(case: dict[str, Any]) -> None:
    assert (
        current_verification(
            case["payload"],
            case["url"],
            datetime.fromisoformat(case["now"]),
        )["state"]
        == case["expected_state"]
    )


class FixedClock(datetime):
    @classmethod
    def now(cls, tz: Any = None) -> Self:
        fixed = cls(
            NOW.year, NOW.month, NOW.day, NOW.hour, NOW.minute, NOW.second,
            NOW.microsecond, tzinfo=NOW.tzinfo, fold=NOW.fold,
        )
        return fixed.replace(tzinfo=None) if tz is None else fixed.astimezone(tz)


ASGI_DAMAGE = [
    ("listing_url", 42),
    ("listing_url", "https://[bad"),
    ("state", None),
    ("state", MISSING),
    ("state", ["active"]),
    ("application_url", {"url": URL}),
    ("application_url", "https://[bad"),
]


@pytest.mark.parametrize("field,value", ASGI_DAMAGE)
def test_corrupt_proof_beside_valid_offer_survives_serializer_list_detail_and_csv(
    export_app: Any,
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    value: Any,
) -> None:
    app, engine = export_app
    identities = sorted(seed(engine, 2))
    monkeypatch.setattr(availability, "datetime", FixedClock)
    repository = JobRepository()
    damaged_payload: dict[str, Any]
    with Session(engine) as session:
        bad = repository.get_job(session, uuid.UUID(identities[0]))
        good = repository.get_job(session, uuid.UUID(identities[1]))
        assert bad is not None and good is not None
        bad_payload = proof(listing_url=bad.url)
        if value is MISSING:
            bad_payload[VERIFICATION_KEY].pop(field)
        else:
            bad_payload[VERIFICATION_KEY][field] = value
        damaged_payload = copy.deepcopy(bad_payload)
        bad.raw_payload = bad_payload
        good.raw_payload = proof(listing_url=good.url)
        session.commit()
        failures = []
        try:
            direct = job_offer_to_read(bad)
            if direct.availability_status != "unverified" or direct.application_url is not None:
                failures.append("direct serializer exposed invalid active proof")
        except (KeyError, ValueError, AttributeError) as error:
            failures.append("direct serializer: " + type(error).__name__)
    metrics = track_stream(app, monkeypatch)
    with TestClient(app, raise_server_exceptions=False) as client:
        client.cookies.set(SESSION_COOKIE_NAME, create_session_token(1))
        listing = client.get("/jobs?profile=engineering&radar=all")
        if listing.status_code != 200:
            failures.append(f"list HTTP {listing.status_code}")
        else:
            items = {v["id"]: v for v in listing.json()["items"]}
            if len(items) != 2 or items[identities[0]]["availability_status"] != "unverified":
                failures.append("list availability contract")
            assert items[identities[1]]["availability_status"] == "active"
        for identity in identities:
            detail = client.get("/jobs/" + identity)
            if detail.status_code != 200:
                failures.append(f"detail HTTP {detail.status_code}")
            else:
                expected = "unverified" if identity == identities[0] else "active"
                if detail.json()["availability_status"] != expected:
                    failures.append("detail availability contract")
                if identity == identities[0] and detail.json()["application_url"] is not None:
                    failures.append("detail exposed invalid application URL")
        response = client.get("/jobs/export?profile=engineering&radar=all")
        reader = csv.DictReader(io.StringIO(response.text.lstrip("\ufeff")))
        rows = {v["id"]: v for v in reader}
        if response.status_code != 200 or set(rows) != set(identities):
            failures.append("CSV missing offer/failed stream")
        else:
            assert len(reader.fieldnames or []) == 36
            if rows[identities[0]]["availability_state"] != "unverified":
                failures.append("CSV exposed invalid active proof")
            if rows[identities[0]]["application_url"]:
                failures.append("CSV exposed invalid application URL")
            assert rows[identities[1]]["availability_state"] == "active"
    assert_closed(metrics)
    with Session(engine) as session:
        saved = repository.get_job(session, uuid.UUID(identities[0]))
        assert saved is not None and saved.raw_payload == damaged_payload
    assert not failures, failures
