"""Regressions grounded in the public employer pages checked on 2026-10-22."""

from __future__ import annotations

import asyncio
from typing import Any

import httpx
import pytest

from app.models.enums import RemoteType
from app.scoring.evidence import binding_experience, experience_requirements
from app.services.normalizer import JobNormalizer
from app.services.verification import verify_listing
from app.sources.bizneo import BizneoJobSource, BizneoPage
from app.sources.employer_html import EmployerHtmlJobSource


def test_bizneo_attribute_metadata_and_full_requirement_boundaries() -> None:
    source = BizneoJobSource({"structured_metadata": True})
    raw = source._job_from_detail_html(
        '<h1>Backend Developer Java</h1><div title="Ubicación">Madrid</div>'
        '<div title="Salario">30.000 € - 50.000 € Bruto/año</div>'
        '<div title="Modalidad de trabajo">Teletrabajo/Remoto</div>'
        '<div class="general-content"><p>Empresa tecnológica con más de 25 años de experiencia.</p>'
        "<p>Desarrollar microservicios Java y APIs REST.</p></div>"
        '<div class="general-content"><ul><li>Al menos 4 años de experiencia backend.</li></ul>'
        "<p>Se valorará especialmente:</p><ul><li>Frontend para ajustes puntuales.</li></ul></div>",
        "https://jobs.experienceis.com/jobs/backend-java",
        BizneoPage("https://jobs.experienceis.com/jobs", None, "Spain"),
    )
    assert raw is not None
    normalized = JobNormalizer().normalize(raw)
    assert normalized.location == "Madrid, Spain"
    assert normalized.remote_type == RemoteType.REMOTE
    assert (normalized.salary_min, normalized.salary_max) == (30000, 50000)
    assert normalized.experience_min_years == 4
    assert "Se valorará especialmente:\nFrontend" in (normalized.requirements or "")


def test_bizneo_title_budget_keeps_ambiguous_software_title_without_javascript_java_match() -> None:
    source = BizneoJobSource(
        {
            "base_url": "https://jobs.experienceis.com",
            "prefilter_titles": True,
            "title_required_any_keywords": ["java", "software"],
        }
    )
    assert source._job_urls_from_html(
        '<a class="job-card" href="/jobs/js"><span class="title">JavaScript</span></a>'
        '<a class="job-card" href="/jobs/software"><span class="title">Software Engineer</span></a>'
    ) == ["https://jobs.experienceis.com/jobs/software"]


def test_company_tenure_does_not_override_real_candidate_experience() -> None:
    requirements = experience_requirements(
        "Empresa tecnológica con más de 25 años de experiencia en el sector IT.\n"
        "Experiencia de 4 años como Desarrollador Backend Java."
    )
    binding = binding_experience(requirements)
    assert binding and binding.minimum == 4


def test_explicit_madrid_office_requirement_outranks_wrong_sevilla_board_header() -> None:
    source = BizneoJobSource({"structured_metadata": True})
    raw = source._job_from_detail_html(
        '<h1>Desarrollador Backend Java. Madrid</h1><div title="Ubicación">Sevilla</div>'
        '<div title="Modalidad de trabajo">Híbrido</div>'
        '<div class="general-content"><ul><li>Modalidad: Híbrido Madrid</li>'
        "<li>Desarrollo de servicios backend en Java.</li></ul></div>",
        "https://jobs.experienceis.com/jobs/java-madrid",
        BizneoPage("index", None, "Spain"),
    )
    assert raw is not None and raw.location == "Madrid, Spain"


def employer_source() -> EmployerHtmlJobSource:
    return EmployerHtmlJobSource(
        {
            "base_url": "https://www.sngular.com",
            "company_name": "SNGULAR",
            "link_selector": "a[href]",
            "description_selector": "section.duties",
            "location_selector": ".location",
            "mode_selector": ".mode",
            "title_required_any_keywords": ["java", "software"],
        }
    )


def test_employer_html_uses_visible_duties_instead_of_incomplete_jsonld() -> None:
    source = employer_source()
    raw = source._parse(
        '<script type="application/ld+json">{"@type":"JobPosting",'
        '"name":"Java Developer", "description":"Company benefits\nonly"}</script>'
        '<h1>Java Developer</h1><div class="location">España</div>'
        '<div class="mode">Remoto 100%</div>'
        '<section class="duties"><p>Desarrollar APIs REST con Spring Boot.</p>'
        "<ul><li>Apache Kafka avanzado innegociable.</li></ul></section>",
        "https://www.sngular.com/es/talento-y-cultura/jobs/77/java-developer",
    )
    assert raw is not None and "Apache Kafka" in raw.description
    assert raw.remote_type == RemoteType.REMOTE and raw.location == "España"
    assert source._links(
        '<a href="/jobs/java">Java Developer</a>'
        '<a href="https://external.example/java">Java Developer</a>'
        '<a href="/jobs/javascript">JavaScript</a>',
        "https://www.sngular.com/jobs",
    ) == ["https://www.sngular.com/jobs/java"]
    assert source._parse("<h1>Java Developer</h1>", "https://www.sngular.com/jobs/java") is None


@pytest.mark.parametrize(
    "variant,expected",
    [
        ("open", "active"),
        ("wrong_job", "listing_only"),
        ("no_cv", "listing_only"),
        ("disabled", "listing_only"),
    ],
)
def test_bizneo_verifies_only_observed_job_bound_candidate_form(
    variant: str,
    expected: str,
) -> None:
    listing = "https://jobs.experienceis.com/jobs/backend-java"
    calls: list[str] = []

    async def run() -> dict[str, Any]:
        def handle(request: httpx.Request) -> httpx.Response:
            assert request.method == "GET"
            calls.append(str(request.url))
            if request.url.path == "/registration/new":
                upload = (
                    (
                        '<div data-component-filepicker="box" name="user[assets][file]" required>'
                        "</div>"
                    )
                    if variant != "no_cv"
                    else ""
                )
                disabled = "disabled" if variant == "disabled" else ""
                return httpx.Response(
                    200,
                    text=(
                        '<form method="post" action="/registration?job_id=backend-java">'
                        '<input type="email">'
                        + upload
                        + f'<button type="submit" {disabled}>Enviar candidatura</button></form>'
                    ),
                )
            job_id = "different" if variant == "wrong_job" else "backend-java"
            return httpx.Response(
                200,
                text=(
                    '<h1>Backend Java</h1><div id="job-inscription" '
                    f'hx-get="/registration/new?job_id={job_id}"></div>'
                ),
            )

        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
            return await verify_listing(client, listing, "Backend Java")

    proof = asyncio.run(run())
    assert proof["state"] == expected
    assert len(calls) == (1 if variant == "wrong_job" else 2)
    if expected == "active":
        assert proof["evidence_level"] == "application_form"


def test_sngular_form_preserves_human_consent_and_captcha_requirement() -> None:
    async def run() -> dict[str, Any]:
        def handle(request: httpx.Request) -> httpx.Response:
            assert request.method == "GET"
            return httpx.Response(
                200,
                text=(
                    '<h1>Java Developer</h1><form action="/es/talent-form">'
                    '<input name="talent[title]" value="Java Developer">'
                    '<input type="email"><input type="file">'
                    '<button disabled type="submit" data-talent-target="btnSubmit">Enviar</button>'
                    "</form>"
                ),
            )

        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
            return await verify_listing(
                client, "https://www.sngular.com/jobs/java", "Java Developer"
            )

    proof = asyncio.run(run())
    assert proof["state"] == "active" and "CAPTCHA" in proof["reason"]
