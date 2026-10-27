from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime
from typing import Any

import pytest

from app.core.availability import VERIFICATION_KEY
from app.core.experience import professional_months
from app.models.enums import RemoteType
from app.scoring.alignment import analyze_work
from app.scoring.engine import ScoringEngine
from app.scoring.evidence import binding_experience, experience_requirements
from app.scoring.salary import extract_salary
from app.scoring.text import canonical_url, detect_remote_type, extract_experience_years
from app.services.normalizer import JobNormalizer, NormalizedJob
from app.sources.base import RawJob

TODAY = date(2026, 10, 21)


def job(**changes: Any) -> NormalizedJob:
    raw = RawJob(
        source_name="synthetic",
        source_job_id="test",
        company_name="Example",
        title="Java Backend Developer",
        description=(
            "Build Java Spring Boot REST APIs with SQL, PostgreSQL, Docker, Linux and CI/CD. "
            "Design distributed services on AWS with Terraform and messaging. "
            "Mentorship and career progression."
        ),
        requirements="2 years of experience. English B2.",
        location="Remote Spain",
        country="Spain",
        remote_type=RemoteType.REMOTE,
        salary_original_text="30000-35000 EUR annual",
        publication_date=datetime(2026, 10, 20, tzinfo=UTC),
    )
    return replace(JobNormalizer().normalize(raw), **changes)


def score(offer: NormalizedJob, as_of: date = TODAY) -> Any:
    return ScoringEngine(as_of=as_of).score(offer)


@pytest.mark.parametrize(
    ("when", "months"),
    [
        (date(2026, 10, 21), 14),
        (date(2027, 8, 1), 24),
        (date(2028, 8, 1), 36),
        (date(2030, 8, 1), 60),
        (date(2025, 7, 1), 0),
    ],
)
def test_professional_tenure_at_requested_milestones(when: date, months: int) -> None:
    assert professional_months("2025-08", when) == months


def test_ranking_prefers_viable_backend_over_technology_rich_senior() -> None:
    current = score(job())
    senior = score(
        job(title="Senior Java Architect", requirements="Required: 8 years of experience")
    )
    assert current.score > senior.score
    assert current.assessment["radar"] == "current"
    assert senior.assessment["radar"] == "strategic"
    assert senior.assessment["category"] == "C"
    assert set(("professional_fit", "growth", "viability")) <= current.assessment.keys()
    assert current.assessment["heuristic_only"] is True


def test_fit_evolves_with_tenure_without_inventing_seniority() -> None:
    offer = job(requirements="Required: 3 years of Java experience", publication_date=None)
    early, later = score(offer), score(offer, date(2028, 8, 1))
    assert later.assessment["professional_fit"] > early.assessment["professional_fit"]
    assert score(job(title="Staff Engineer Java"), date(2030, 8, 1)).assessment["category"] == "C"


def test_experience_uses_lower_range_and_distinguishes_desirable() -> None:
    offer = job(
        requirements="Required: 2-3 years Java experience. Preferred: 8 years of AWS experience."
    )
    result = score(offer)
    assert result.assessment["radar"] == "current"
    assert extract_experience_years(offer.requirements or "") == (2, 3)
    assert [x["kind"] for x in result.assessment["experience_requirements"]] == [
        "mandatory",
        "desirable",
    ]


def test_company_age_and_benefits_are_not_candidate_experience() -> None:
    items = experience_requirements(
        "Our company has 20 years of Java experience. 3 years paid sabbatical. "
        "Required: 2 years of backend experience."
    )
    binding = binding_experience(items)
    assert binding is not None and binding.minimum == 2
    assert (
        experience_requirements(
            "Trabajaras en un entorno con mas de 35 anos de experiencia en digitalizacion."
        )
        == []
    )


@pytest.mark.parametrize(
    ("place", "mode", "expected", "scope"),
    [
        ("Remote Spain", RemoteType.REMOTE, "compatible", "spain"),
        ("Remote Europe", RemoteType.REMOTE, "uncertain", "europe"),
        ("Worldwide", RemoteType.REMOTE, "uncertain", "worldwide"),
        ("Remote US only", RemoteType.REMOTE, "incompatible", "country_restricted"),
        ("Remote Poland", RemoteType.REMOTE, "incompatible", "country_restricted"),
        ("Madrid", RemoteType.HYBRID, "incompatible", "relocation"),
        ("Sevilla", RemoteType.HYBRID, "compatible", "local"),
    ],
)
def test_remote_scope_and_residence_are_separate(
    place: str,
    mode: RemoteType,
    expected: str,
    scope: str,
) -> None:
    result = score(job(location=place, remote_type=mode))
    assert result.assessment["location_status"] == expected
    assert result.assessment["remote_scope"] == scope


def test_remote_europe_with_explicit_residence_restriction_is_excluded() -> None:
    result = score(
        job(location="Remote Europe", description="Build Java APIs. You must be based in Germany.")
    )
    assert "location_incompatible" in result.assessment["blockers"]


def test_remote_spain_does_not_override_required_residence_in_galicia() -> None:
    result = score(
        job(
            location="Spain",
            description=("Build Java APIs. Es importante que el candidato/a resida en Galicia."),
        )
    )
    assert "location_incompatible" in result.assessment["blockers"]


def test_residence_region_requirement_survives_optional_city_preference() -> None:
    result = score(
        job(
            location="Spain",
            description=(
                "Build Java Spring Boot APIs. Residencia en Galicia, preferiblemente en la zona de "
                "A Coruna, con disponibilidad para acudir puntualmente a oficina."
            ),
        )
    )
    assert result.assessment["radar"] == "excluded"


@pytest.mark.parametrize("title", ["Líder técnico Java", "Java Developer"])
def test_explicit_lead_or_expert_level_is_a_future_reference(title: str) -> None:
    result = score(
        job(title=title, description="Build Java Spring Boot APIs. Level: Advanced (expert).")
    )
    assert result.assessment["radar"] == "strategic" and result.score <= 59


def test_frontend_employment_years_are_not_implied_by_backend_experience() -> None:
    result = score(
        job(requirements="Minimum 2 years of frontend framework experience. Java Spring Boot.")
    )
    assert result.score <= 59


def test_spanish_between_year_range_uses_its_lower_bound() -> None:
    item = binding_experience(experience_requirements("Experiencia entre 3 y 5 anos en Java."))
    assert item and item.minimum == 3 and item.maximum == 5


@pytest.mark.parametrize("phrase", ["Experiencia de hasta 3 anos", "Up to 3 years of experience"])
def test_experience_upper_limit_is_not_a_required_minimum(phrase: str) -> None:
    requirement = binding_experience(experience_requirements(phrase))
    assert requirement is not None
    assert requirement.minimum == 0 and requirement.maximum == 3


def test_hybrid_with_remote_days_is_not_full_remote() -> None:
    raw = RawJob(
        source_name="synthetic",
        source_job_id="hybrid",
        company_name="Example",
        title="Java Developer",
        description="Hybrid Madrid. Two remote days. Build Java APIs.",
        location="Madrid",
        remote_type=RemoteType.REMOTE,
    )
    offer = JobNormalizer().normalize(raw)
    assert offer.remote_type == RemoteType.HYBRID
    assert score(offer).assessment["radar"] == "excluded"


def test_remote_source_with_onsite_interview_is_still_remote() -> None:
    assert (
        detect_remote_type("Build APIs. Remote Europe. On-site interviews.", RemoteType.REMOTE)
        == RemoteType.REMOTE
    )


def test_required_office_work_overrides_remote_portal_label() -> None:
    assert (
        detect_remote_type("Remote. Must work in the office 3 days per week.", RemoteType.REMOTE)
        == RemoteType.HYBRID
    )
    assert detect_remote_type("Build APIs using remote debugging.") == RemoteType.UNKNOWN


@pytest.mark.parametrize("technology", ["Golang", ".NET", "C#", "C++", "Rust"])
def test_mandatory_unfamiliar_stack_uses_real_word_boundaries(technology: str) -> None:
    result = score(job(requirements=f"{technology} required for production software."))
    assert "mandatory_stack_mismatch" in result.assessment["blockers"]


def test_java_is_not_javascript_and_negated_java_does_not_add_fit() -> None:
    javascript = score(
        job(title="JavaScript Developer", description="Build JavaScript APIs.", requirements=None)
    )
    negated = score(
        job(
            title="Backend Developer",
            description="We no longer use Java. Build Node.js APIs.",
            requirements=None,
        )
    )
    assert javascript.assessment["radar"] == "excluded"
    assert negated.assessment["radar"] == "excluded"


def test_java_in_a_language_list_does_not_make_ai_task_work_a_backend_job() -> None:
    result = score(
        job(
            title="Software Engineer, Coding Tasks",
            description="Build AI coding tasks from your repository. Java or Python or Rust.",
            requirements="2 years of software engineering.",
        )
    )
    assert result.assessment["radar"] == "excluded"


def test_required_french_is_a_blocker_but_desirable_french_is_not() -> None:
    required = score(job(title="Java Developer con Frances"))
    desirable = score(job(requirements="French preferred. 2 years of Java experience."))
    assert "unsupported_language" in required.assessment["blockers"]
    assert desirable.assessment["radar"] == "current"


def test_keywords_alone_do_not_grant_cloud_transition_or_growth() -> None:
    result = score(
        job(
            title="Cloud Engineer",
            description="AWS Kubernetes Terraform monitoring.",
            requirements=None,
        )
    )
    assert result.assessment["recommendation"] == "U"
    assert result.assessment["growth"] == 0


def test_platform_development_is_a_growth_path_but_operations_is_not() -> None:
    developer = score(
        job(
            title="Platform Engineer",
            description="Develop platform APIs and automate tools with AWS and Terraform.",
        )
    )
    operator = score(
        job(
            title="DevOps Engineer",
            description="Primarily monitoring and support of AWS and Kubernetes.",
        )
    )
    assert developer.assessment["category"] == "B"
    assert developer.assessment["radar"] == "current"
    assert operator.assessment["radar"] == "excluded"


@pytest.mark.parametrize(
    ("minimum", "maximum", "expected"),
    [
        (21000, 23000, "below_minimum"),
        (23000, 26000, "overlapping_minimum"),
        (24000, 25000, "minimum_met"),
        (30000, 35000, "target_or_above"),
        (None, 33000, "overlapping_minimum"),
        (None, 23000, "below_minimum"),
    ],
)
def test_salary_respects_minimum_without_inventing_acceptance(
    minimum: int | None,
    maximum: int,
    expected: str,
) -> None:
    result = score(job(salary_min=minimum, salary_max=maximum))
    assert result.assessment["salary_status"] == expected
    assert (result.assessment["radar"] == "excluded") == (expected == "below_minimum")


def test_unknown_salary_remains_eligible_and_foreign_currency_has_no_fake_conversion() -> None:
    unknown = score(job(salary_min=None, salary_max=None, salary_unknown=True))
    foreign = score(job(salary_currency="USD"))
    assert unknown.assessment["radar"] == "current"
    assert unknown.assessment["salary_evidence"] == "unknown"
    assert foreign.assessment["salary_status"] == "published_not_comparable"


def test_expiry_and_staleness_reduce_viability_even_when_stack_matches() -> None:
    fresh = score(job())
    old = score(job(publication_date=datetime(2026, 1, 1, tzinfo=UTC)))
    expired = score(job(expiration_date=datetime(2026, 10, 20, tzinfo=UTC)))
    assert old.assessment["viability"] < fresh.assessment["viability"]
    assert expired.assessment["radar"] == "excluded"
    assert expired.assessment["freshness"] == "expired"


def test_cloud_projects_and_certificates_do_not_satisfy_professional_years() -> None:
    result = score(job(requirements="Required: 5 years of professional AWS experience."))
    assert result.assessment["professional_months"] == 14
    assert result.assessment["viability"] <= 45
    assert any("certificaciones" in reason for reason in result.assessment["uncertainties"])


def test_c1_goal_does_not_satisfy_required_c1() -> None:
    b2 = score(job(requirements="English B2 required. 2 years backend experience."))
    c1 = score(job(requirements="English C1 required. 2 years backend experience."))
    assert c1.assessment["viability"] < b2.assessment["viability"]
    assert c1.assessment["english_requirement"] == "above_certified_b2"


def test_unknown_mandatory_stack_is_different_from_desirable_stack() -> None:
    required = score(job(requirements="Golang required. 2 years backend experience."))
    desirable = score(job(requirements="Golang preferred. 2 years backend experience."))
    assert required.assessment["radar"] == "excluded"
    assert desirable.assessment["radar"] == "current"


def test_canonical_urls_remove_tracking_and_preserve_job_identity() -> None:
    assert (
        canonical_url("https://EXAMPLE.test/job?id=42&utm_source=board&gh_src=abc#form")
        == "https://example.test/job?id=42"
    )
    assert canonical_url("https://example.test/job?id=43") != canonical_url(
        "https://example.test/job?id=42"
    )


@pytest.mark.parametrize("description,compatible", [
    ("Hybrid Madrid. Remote from other locations within Spain.", True),
    ("Hybrid Madrid. Remoto desde el resto de Espana.", True),
    ("Remote from other locations within Spain. Must attend the office weekly.", False),
    ("Hybrid Madrid. Two remote days per week.", False),
])
def test_explicit_remote_alternative_for_other_spanish_locations(
    description: str, compatible: bool
) -> None:
    offer = job(location="Madrid, Spain", remote_type=RemoteType.HYBRID,
                description="Build Java Spring Boot APIs. " + description)
    result = score(offer)
    assert (result.assessment["location_status"] == "compatible") is compatible


def test_country_in_remote_job_title_overrides_worldwide_portal_metadata() -> None:
    result = score(job(title="Java Engineer (Remote @ Colombia)",
                       location="Worldwide", country="Worldwide"))
    assert result.assessment["location_status"] == "incompatible"
    assert result.assessment["radar"] == "excluded"


def test_internal_selection_is_not_an_external_opportunity() -> None:
    result = score(job(description="Build Java Spring APIs. Processo Seletivo Interno."))
    assert "internal_only" in result.assessment["blockers"]
    assert result.assessment["radar"] == "excluded"


def test_explicit_unspecified_work_mode_is_uncertain_despite_remote_metadata() -> None:
    result = score(job(description="Build Java APIs. "
                       "Ubicacion, modalidad de trabajo y duracion: No especificadas."))
    assert result.assessment["location_status"] == "uncertain"
    assert result.assessment["radar"] == "current"


def active_job(**changes: Any) -> NormalizedJob:
    offer = job(**changes)
    offer.raw_payload[VERIFICATION_KEY] = {
        "state": "active", "listing_url": offer.url,
        "checked_at": datetime.now(UTC).isoformat(),
        "application_url": offer.url, "evidence_level": "application_form",
        "reason": "Public application form accessible",
    }
    return offer


def test_infrastructure_developer_platform_is_not_software_development() -> None:
    operator = score(active_job(
        title="DevOps Engineer",
        description="Support and maintain foundational infrastructure and developer tools. "
                    "Improve the developer platform for fast and secure software delivery. "
                    "Manage AWS infrastructure, Linux servers and CI/CD pipelines.",
        requirements="At least 2 years of DevOps experience."))
    backend = score(active_job())
    assert operator.assessment["recommendation"] == "D"
    assert operator.assessment["work_focus"] == "operations"
    assert not operator.assessment["software_work_evidence"]
    assert backend.score > operator.score


def test_platform_api_engineering_remains_an_eligible_secondary_path() -> None:
    platform = score(active_job(title="Platform Engineer",
        description="Develop platform APIs and design distributed software on AWS."))
    backend = score(active_job())
    assert platform.assessment["recommendation"] == "B"
    assert platform.assessment["career_alignment"] < backend.assessment["career_alignment"]
    assert platform.score < backend.score


@pytest.mark.parametrize("requirements,gap", [
    ("Buscamos experiencia en\nKotlin\nJava\nSpring Boot", "Kotlin"),
    ("Requirements\nPython\nJava\nUnrelated office or remote policy", "Python"),
    ("Must to have skills\nAngular\nNice to have skills\nGerman Language", "Angular"),
    ("Experiencia con AWS Serverless y Terraform.", "AWS"),
])
def test_required_lists_preserve_specialist_gaps(requirements: str, gap: str) -> None:
    result = score(active_job(requirements=requirements))
    assert any(x.startswith(gap + ":") for x in
               result.assessment["specialist_requirements_to_confirm"])
    assert result.assessment["recommendation"] != "A"


@pytest.mark.parametrize("requirements", [
    "Buscamos\nExperiencia en Java y/o Kotlin",
    "Requirements\nJava or Kotlin\nNice to have skills\nPython",
    "Python preferred. 2 years of Java experience.",
])
def test_alternatives_and_desirable_requirements_do_not_create_false_gaps(
    requirements: str,
) -> None:
    result = score(active_job(requirements=requirements))
    assert not result.assessment["specialist_requirements_to_confirm"]
    assert result.assessment["recommendation"] == "A"


def test_backend_years_do_not_satisfy_independent_frontend_experience() -> None:
    result = score(active_job(requirements="2 years of React experience required."))
    assert result.assessment["recommendation"] == "U"
    assert result.assessment["independent_professional_experience"]


@pytest.mark.parametrize("requirements", [
    "Required: 5 years of Java experience.", "Buscamos un perfil senior en Java.",
])
def test_five_year_and_body_senior_roles_are_strategic(requirements: str) -> None:
    result = score(active_job(requirements=requirements))
    assert result.assessment["recommendation"] == "C"
    assert result.assessment["radar"] == "strategic"


def test_unverified_form_is_insufficient_even_with_strong_technical_fit() -> None:
    result = score(job())
    assert result.assessment["recommendation"] == "U"
    assert result.assessment["professional_fit"] >= 80


def test_enterprise_integration_and_erp_are_not_negative_career_signals() -> None:
    result = score(active_job(description="Develop Java Spring backend APIs and ERP "
        "integrations. Design distributed services and messaging."))
    assert result.assessment["recommendation"] == "A"


def test_sparse_real_spanish_developer_duties_are_retained() -> None:
    work = analyze_work("Software Developer Java",
        "Participaras en desarrollos de proyectos asumiendo un rol de desarrollador Java.",
        {"Java"}, [])
    assert work.focus == "backend"


def test_community_size_is_not_a_salary_even_near_funding_currency() -> None:
    result = extract_salary("540000 community members. Raised $500M in funding.")
    assert result.salary_min is None
    assert result.unknown


def test_hours_and_certification_numbers_are_not_pay_evidence() -> None:
    result = extract_salary("Working hours 09:00 - 18:00. Salary: 40,000-43,000 EUR annual.")
    assert (result.salary_min, result.salary_max) == (40000, 43000)
    assert extract_salary("ISO/IEC 27001. Benefits: competitive compensation.").unknown
    assert extract_salary("Competitive salary. 28 days paid annual leave.").unknown


def test_employee_k_salary_range_is_separate_from_freelance_day_rate() -> None:
    result = extract_salary("Freelance: 280 EUR per day. Contrato indefinido: 45k-47k.")
    assert (result.salary_min, result.salary_max) == (45000, 47000)


def test_remote_latam_title_overrides_worldwide_metadata() -> None:
    result = score(active_job(title="Java Engineer - Latin America - Remote",
                              location="Worldwide", country="Worldwide"))
    assert result.assessment["recommendation"] == "D"
    assert result.assessment["location_status"] == "incompatible"


def test_preferred_years_heading_is_not_a_mandatory_five_year_requirement() -> None:
    result = score(active_job(requirements="Nice to have\n5 years of AWS experience."))
    assert result.assessment["recommendation"] == "A"
    assert result.assessment["experience_requirements"][0]["kind"] == "desirable"


def test_mirror_senior_tag_does_not_override_actual_job_requirements() -> None:
    result = score(active_job(requirements="2 years of Java experience.\nJava-Developer, Senior"))
    assert result.assessment["recommendation"] == "A"


def test_explicit_hiring_country_list_is_stronger_than_worldwide_metadata() -> None:
    result = score(active_job(location="Worldwide", country="Worldwide",
        description="Develop and test new functionality in Java. "
        "We are open to applicants based in the UK, Netherlands, Belgium, France and Germany."))
    assert result.assessment["work_focus"] == "backend"
    assert result.assessment["recommendation"] == "D"
    assert "location_incompatible" in result.assessment["blockers"]
