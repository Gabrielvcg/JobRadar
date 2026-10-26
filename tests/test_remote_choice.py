"""The live Marfeel choice clause, with mandatory-attendance counterexamples."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from app.models.enums import RemoteType
from app.scoring.geography import assess_location
from app.scoring.text import detect_remote_type
from app.services.normalizer import JobNormalizer
from app.sources.base import RawJob


def marfeel() -> dict[str, Any]:
    value: dict[str, Any] = json.loads(
        (Path(__file__).parent / "fixtures/marfeel-remote-choice.json").read_text(encoding="utf-8")
    )
    return value


def test_marfeel_offers_full_remote_as_a_choice_without_inventing_country() -> None:
    evidence = marfeel()
    raw = RawJob(
        source_name="review_only",
        source_job_id="246",
        company_name="Marfeel",
        title=evidence["title"],
        description=evidence["mode_excerpt"],
        location=evidence["location"],
        country=evidence["country"] or None,
        url=evidence["source_url"],
        remote_type=RemoteType.REMOTE,
    )
    normalized = JobNormalizer().normalize(raw)
    assert normalized.remote_type == RemoteType.REMOTE
    assert normalized.country is None
    assert normalized.location == "Barcelona, Remote"
    assert normalized.experience_min_years is None
    assert normalized.salary_unknown
    location = assess_location(
        normalized.location, normalized.country, normalized.remote_type,
        normalized.description, ["Sevilla"],
    )
    assert location.status != "compatible"
    assert location.scope == "country_restricted"


@pytest.mark.parametrize("fallback", [RemoteType.UNKNOWN, RemoteType.REMOTE])
def test_complete_choice_is_sufficient_remote_evidence(fallback: RemoteType) -> None:
    assert detect_remote_type(marfeel()["mode_excerpt"], fallback) == RemoteType.REMOTE


@pytest.mark.parametrize(
    "text,expected",
    [
        # Existing regression cases: optional telework does not erase hybrid duties.
        ("Hybrid Madrid. Two remote days. Build Java APIs.", RemoteType.HYBRID),
        ("Remote. Must work in the office 3 days per week.", RemoteType.HYBRID),
        ("Build APIs. Remote Europe. On-site interviews.", RemoteType.REMOTE),
        # Additional counterfactuals around the actual employer option clause.
        ("Fully remote during onboarding, hybrid afterwards.", RemoteType.HYBRID),
        ("Choose remote/hybrid, but client requires two days at office.", RemoteType.HYBRID),
        (
            "Option to work full remote, hybrid or office-based. "
            "The client requires two days at office.",
            RemoteType.HYBRID,
        ),
        (
            "Option to work full remote, hybrid or office-based, subject to client approval.",
            RemoteType.HYBRID,
        ),
        (
            "Option to work full remote, hybrid or office-based. "
            "Must work in the office 3 days per week.",
            RemoteType.HYBRID,
        ),
        (
            "Candidate preference: full remote. This position is hybrid in Madrid.",
            RemoteType.HYBRID,
        ),
        (
            "Option to work full remote, hybrid or office-based. No remote for this project.",
            RemoteType.ONSITE,
        ),
        (
            "Option to work full remote, hybrid or office-based. "
            "Full remote is available only to the Sales department.",
            RemoteType.HYBRID,
        ),
        (
            "Option to work full remote, hybrid or office-based (if in BCN area), "
            "subject to client approval.",
            RemoteType.HYBRID,
        ),
    ],
)
def test_mandatory_attendance_and_interview_regressions(text: str, expected: RemoteType) -> None:
    assert detect_remote_type(text, RemoteType.REMOTE) == expected


def test_choice_does_not_override_explicit_hybrid_location_metadata() -> None:
    assert detect_remote_type(
        marfeel()["mode_excerpt"], RemoteType.REMOTE, location="Madrid, hybrid",
    ) == RemoteType.HYBRID


@pytest.mark.parametrize(
    "condition",
    ["Full remote requires client approval.", "Remote work is subject to client approval."],
)
def test_separate_client_approval_clause_preserves_geography_block(condition: str) -> None:
    description = marfeel()["mode_excerpt"] + ". " + condition
    mode = detect_remote_type(description, RemoteType.REMOTE, location="Remote Spain")
    assert mode == RemoteType.HYBRID
    result = assess_location("Remote Spain", "Spain", mode, description, ["Sevilla"])
    assert result.status == "incompatible" and result.points == 0


@pytest.mark.parametrize("place,scope", [(None, "unknown"), ("Remote Europe", "europe")])
def test_remote_choice_does_not_establish_country_eligibility(
    place: str | None, scope: str,
) -> None:
    description = marfeel()["mode_excerpt"]
    mode = detect_remote_type(description)
    result = assess_location(place, None, mode, description, ["Sevilla"])
    assert mode == RemoteType.REMOTE
    assert result.status == "uncertain" and result.scope == scope
