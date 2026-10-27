"""Regression from a new official vacancy ingested on 2026-10-23."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.core.availability import VERIFICATION_KEY
from app.scoring.alignment import analyze_work
from app.scoring.engine import ScoringEngine
from app.services.normalizer import JobNormalizer
from app.sources.base import RawJob


def test_primary_application_operations_is_not_a_recommended_java_candidacy() -> None:
    url = (
        "https://knowmadmood.teamtailor.com/jobs/"
        "8594415-ingeniero-a-de-soporte-de-aplicaciones-java-remoto"
    )
    declaration = (
        "La posición tiene un componente técnico orientado principalmente "
        "a la operación y soporte, "
        "combinando tareas de monitorización, análisis y resolución de problemas "
        "con desarrollo en Java."
    )
    raw = RawJob(
        source_name="knowmad_official",
        source_job_id="8594415",
        company_name="knowmad mood",
        title="Ingeniero/a de Soporte de Aplicaciones Java | Remoto",
        url=url,
        location="Spain",
        description=(
            declaration + "\nResponsabilidades\n"
            "Monitorización de aplicaciones y servicios en entornos productivos.\n"
            "Desarrollar pequeñas correcciones sobre las aplicaciones Java.\n"
            "Analizar incidencias de producción y revisar logs.\n"
            "Requisitos\nExperiencia con Java, Spring Boot y APIs REST."
        ),
        raw_payload={
            VERIFICATION_KEY: {
                "state": "active",
                "listing_url": url,
                "application_url": url + "/applications/new",
                "checked_at": datetime.now(UTC).isoformat(),
                "evidence_level": "application_form",
            }
        },
    )
    result = ScoringEngine().score(JobNormalizer().normalize(raw))
    assert result.assessment is not None
    assert result.assessment["work_focus"] == "operations"
    assert result.assessment["software_work_evidence"]  # Corrective coding is still acknowledged.
    assert declaration.rstrip(".") in result.assessment["operations_work_evidence"]
    assert result.assessment["recommendation"] == "D"
    assert "career_direction_mismatch" in result.assessment["blockers"]


@pytest.mark.parametrize(
    "declaration",
    [
        "El puesto no está orientado principalmente a la operación y soporte.",
        "El rol no está enfocado principalmente en el soporte.",
        "El puesto está orientado principalmente al desarrollo de microservicios.",
    ],
)
def test_negated_or_software_primary_work_is_not_excluded(declaration: str) -> None:
    work = analyze_work(
        "Java Backend Developer",
        declaration + "\nResponsabilidades\nDiseñar APIs y desarrollar microservicios Java.\n"
        "Colaborar con soporte para diagnosticar incidencias de las aplicaciones.",
        {"Java", "Spring Boot"},
        [],
    )
    assert work.focus == "backend"
