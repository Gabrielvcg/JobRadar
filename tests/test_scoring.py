from __future__ import annotations

from datetime import UTC, datetime

from app.models.enums import RemoteType
from app.scoring.engine import ScoringEngine
from app.services.normalizer import NormalizedJob


def test_scores_strong_backend_cloud_offer_highly() -> None:
    job = _job(
        title="Backend Engineer Java AWS",
        description="Java Spring Boot REST APIs PostgreSQL Docker AWS Terraform GitHub Actions",
        technologies=["Java", "Spring Boot", "REST", "PostgreSQL", "Docker", "AWS", "Terraform"],
        salary_min=32000,
        salary_max=35000,
        remote_type=RemoteType.REMOTE,
        location="Remote from Spain",
    )

    result = ScoringEngine().score(job)

    assert result.score >= 80
    assert result.level == "excellent"
    assert result.positive


def test_penalizes_low_salary_helpdesk_offer() -> None:
    job = _job(
        title="Helpdesk Technician Tier 1",
        description="Helpdesk tickets and basic support. Salary 18,000 EUR/year",
        technologies=[],
        salary_min=18000,
        salary_max=18000,
        remote_type=RemoteType.ONSITE,
        location="Sevilla onsite",
    )

    result = ScoringEngine().score(job)

    assert result.score < 50
    assert result.level == "low"
    assert any("salario" in reason.lower() for reason in result.negative)
    assert any("helpdesk" in reason.lower() for reason in result.negative)


def test_penalizes_senior_high_experience_offer_for_junior_profile() -> None:
    job = _job(
        title="Senior Java React Engineer",
        description="Remote role in English with Java, Spring Boot, React, REST APIs and AWS.",
        technologies=["Java", "Spring Boot", "REST", "AWS"],
        salary_min=45000,
        salary_max=55000,
        remote_type=RemoteType.REMOTE,
        location="Remote",
        requirements="5 years of professional experience",
        experience_min_years=5,
        experience_max_years=5,
    )

    result = ScoringEngine().score(job)

    assert result.score < 65
    assert any("senior" in reason.lower() for reason in result.negative)
    assert any("experiencia" in reason.lower() for reason in result.negative)


def test_java_devops_senior_offer_remains_visible() -> None:
    job = _job(
        title="Java/DevOps Senior Pipelines CI/CD y Docker",
        description="Java pipelines CI/CD Docker cloud platform role.",
        technologies=["Java", "Docker", "CI/CD"],
        salary_min=None,
        salary_max=None,
        remote_type=RemoteType.REMOTE,
        location="Anywhere in the World",
        requirements="4 years of experience",
        experience_min_years=4,
        experience_max_years=4,
    )

    result = ScoringEngine().score(job)

    assert result.score >= 35
    assert any("senior" in reason.lower() for reason in result.negative)


def test_scores_appsec_offer_as_profile_variation() -> None:
    job = _job(
        title="Application Security Engineer",
        description=(
            "Secure development with OWASP, threat modeling, SAST, cloud security, AWS "
            "and CI/CD."
        ),
        technologies=[
            "Application Security",
            "OWASP",
            "Threat Modeling",
            "SAST",
            "Cloud Security",
            "AWS",
            "CI/CD",
        ],
        salary_min=None,
        salary_max=None,
        remote_type=RemoteType.REMOTE,
        location="Remote Europe",
        requirements="3 years of experience",
        experience_min_years=3,
        experience_max_years=3,
    )

    result = ScoringEngine().score(job)

    assert result.score >= 50
    assert any("appsec" in reason.lower() for reason in result.positive)


def test_non_java_backend_with_only_owasp_signal_does_not_rank() -> None:
    job = _job(
        title="Golang Backend Developer",
        description="Build REST APIs with Docker, AWS and OWASP practices.",
        technologies=["REST", "Docker", "AWS", "OWASP"],
        salary_min=None,
        salary_max=None,
        remote_type=RemoteType.REMOTE,
        location="Remote Europe",
        requirements="3 years of experience",
        experience_min_years=3,
        experience_max_years=3,
    )

    result = ScoringEngine().score(job)

    assert result.score < 35
    assert any("java" in reason.lower() for reason in result.negative)


def test_converts_pln_salary_before_low_salary_penalty() -> None:
    job = _job(
        title="Backend Java Engineer",
        description="Build Java Spring Boot APIs.",
        technologies=["Java", "Spring Boot", "REST"],
        salary_min=252000,
        salary_max=297000,
        salary_currency="PLN",
        remote_type=RemoteType.REMOTE,
        location="Remote Poland",
    )

    result = ScoringEngine().score(job)

    assert all("salario" not in reason.lower() for reason in result.negative)
    assert result.score >= 65


def test_penalizes_low_pln_salary_after_conversion() -> None:
    job = _job(
        title="Backend Java Engineer",
        description="Build Java Spring Boot APIs.",
        technologies=["Java", "Spring Boot", "REST"],
        salary_min=60000,
        salary_max=80000,
        salary_currency="PLN",
        remote_type=RemoteType.REMOTE,
        location="Remote Poland",
    )

    result = ScoringEngine().score(job)

    assert result.score < 50
    assert any("salario" in reason.lower() for reason in result.negative)


def test_converts_czk_salary_before_low_salary_penalty() -> None:
    job = _job(
        title="Backend Java Engineer",
        description="Build Java Spring Boot APIs.",
        technologies=["Java", "Spring Boot", "REST"],
        salary_min=1435600,
        salary_max=1635600,
        salary_currency="CZK",
        remote_type=RemoteType.REMOTE,
        location="Remote Czechia",
    )

    result = ScoringEngine().score(job)

    assert all("salario" not in reason.lower() for reason in result.negative)
    assert result.score >= 65


def test_converts_sek_salary_before_scoring() -> None:
    job = _job(
        title="Backend Java Engineer",
        description="Build Java Spring Boot APIs.",
        technologies=["Java", "Spring Boot", "REST"],
        salary_min=775444,
        salary_max=930533,
        salary_currency="SEK",
        remote_type=RemoteType.REMOTE,
        location="Remote Sweden",
    )

    result = ScoringEngine().score(job)

    assert all("salario" not in reason.lower() for reason in result.negative)
    assert result.score >= 65


def test_staff_word_in_description_does_not_trigger_leadership_penalty() -> None:
    job = _job(
        title="Rust & Java Engineer",
        description="Build Java Spring Boot APIs and collaborate with other staff.",
        technologies=["Java", "Spring Boot", "REST"],
        salary_min=None,
        salary_max=None,
        remote_type=RemoteType.REMOTE,
        location="Remote within Europe",
        requirements="4 years of professional experience",
        experience_min_years=4,
        experience_max_years=4,
    )

    result = ScoringEngine().score(job)

    assert all("staff, principal" not in reason.lower() for reason in result.negative)
    assert result.score >= 35


def test_recruiter_word_in_description_does_not_trigger_role_penalty() -> None:
    job = _job(
        title="Java Developer",
        description="Build Java Spring Boot APIs. Our recruiter will get back to you.",
        technologies=["Java", "Spring Boot", "REST"],
        salary_min=None,
        salary_max=None,
        remote_type=RemoteType.REMOTE,
        location="Prague, Czechia",
        requirements="Backend engineering and PostgreSQL.",
        experience_min_years=None,
        experience_max_years=None,
    )

    result = ScoringEngine().score(job)

    assert all("rol no alineado" not in reason.lower() for reason in result.negative)
    assert result.score >= 35


def test_senior_word_in_description_does_not_trigger_senior_penalty() -> None:
    job = _job(
        title="Software Engineer - Backend (Java)",
        description="Build Java services with support from senior mentors.",
        technologies=["Java", "Spring Boot", "REST"],
        salary_min=None,
        salary_max=None,
        remote_type=RemoteType.HYBRID,
        location="Mannheim, Germany",
        requirements="Java and Spring backend engineering.",
        experience_min_years=None,
        experience_max_years=None,
    )

    result = ScoringEngine().score(job)

    assert all("senior" not in reason.lower() for reason in result.negative)
    assert result.score >= 35


def test_production_support_in_backend_description_is_not_helpdesk() -> None:
    job = _job(
        title="Java Software Engineer - Compliance",
        description="Build Java backend services and assist with L2 production support.",
        technologies=["Java", "SQL", "CI/CD", "AWS"],
        salary_min=None,
        salary_max=None,
        remote_type=RemoteType.HYBRID,
        location="Prague, Czechia",
        requirements="3-5 years of Java experience.",
        experience_min_years=3,
        experience_max_years=5,
    )

    result = ScoringEngine().score(job)

    assert all("helpdesk" not in reason.lower() for reason in result.negative)
    assert result.score >= 35


def test_role_fit_does_not_match_api_inside_longer_word() -> None:
    job = _job(
        title="Partnerperspektive Coordinator",
        description="Customer coordination role with stakeholder communication.",
        technologies=[],
        salary_min=None,
        salary_max=None,
        remote_type=RemoteType.REMOTE,
        location="Remote",
        requirements="1 year of experience",
    )

    result = ScoringEngine().score(job)

    assert "El puesto contiene senales de backend o desarrollo de APIs" not in result.positive


def test_high_salary_non_technical_offer_does_not_rank() -> None:
    job = _job(
        title="Steuerberater mit Partnerperspektive",
        description="Tax consulting role with client advisory and high compensation.",
        technologies=[],
        salary_min=90000,
        salary_max=90000,
        remote_type=RemoteType.UNKNOWN,
        location="Germany",
        requirements="Professional tax advisory experience",
        experience_min_years=None,
        experience_max_years=None,
    )

    result = ScoringEngine().score(job)

    assert result.score < 20
    assert any("backend" in reason.lower() for reason in result.negative)


def test_cloud_backend_without_java_stack_drops_below_dashboard_threshold() -> None:
    job = _job(
        title=".NET Developer",
        description="Build REST APIs with CI/CD, GitHub Actions, AWS and Kubernetes.",
        technologies=["REST", "GitHub Actions", "CI/CD", "AWS", "Kubernetes"],
        salary_min=None,
        salary_max=None,
        remote_type=RemoteType.REMOTE,
        location="Spain",
        requirements="Software Engineering",
        experience_min_years=None,
        experience_max_years=None,
    )

    result = ScoringEngine().score(job)

    assert result.score < 35
    assert any("java" in reason.lower() for reason in result.negative)


def test_product_owner_with_platform_signal_does_not_rank() -> None:
    job = _job(
        title="Product Owner Platform",
        description="Own the platform roadmap, stakeholders and delivery metrics.",
        technologies=[],
        salary_min=100000,
        salary_max=100000,
        remote_type=RemoteType.HYBRID,
        location="Köln",
        requirements="3 years of experience with agile teams",
        experience_min_years=3,
        experience_max_years=3,
    )

    result = ScoringEngine().score(job)

    assert result.score < 20
    assert any("rol no alineado" in reason.lower() for reason in result.negative)


def test_engineering_profile_flags_disability_technical_offer() -> None:
    job = _job(
        title="Desarrollador/a Java 100% remoto con discapacidad",
        description=(
            "Desarrollo backend con Java, Spring Boot, microservicios, APIs REST y AWS. "
            "Oferta dirigida a personas con discapacidad."
        ),
        technologies=["Java", "Spring Boot", "REST", "AWS"],
        salary_min=None,
        salary_max=None,
        remote_type=RemoteType.REMOTE,
        location="Madrid, Spain",
        requirements="Certificado de discapacidad oficial igual o superior al 33%. 3 anos.",
        experience_min_years=3,
        experience_max_years=3,
    )

    result = ScoringEngine("engineering").score(job)

    assert result.score >= 65
    assert any("discapacidad" in reason.lower() for reason in result.positive)


def test_engineering_profile_keeps_backend_disability_offer_without_java_visible() -> None:
    job = _job(
        title="Backend Engineer con discapacidad",
        description=(
            "Backend engineering para servicios cloud con Docker, CI/CD y observabilidad. "
            "Oferta dirigida a personas con certificado de discapacidad."
        ),
        technologies=["Docker", "CI/CD", "Observability"],
        salary_min=None,
        salary_max=None,
        remote_type=RemoteType.REMOTE,
        location="Madrid, Spain",
        requirements="Certificado de discapacidad igual o superior al 33%.",
        experience_min_years=None,
        experience_max_years=None,
    )

    result = ScoringEngine("engineering").score(job)

    assert result.score >= 35
    assert all("java" not in reason.lower() for reason in result.negative)


def test_engineering_profile_keeps_non_technical_disability_offer_low() -> None:
    job = _job(
        title="Administrativo/a con discapacidad",
        description="Gestion documental, archivo y atencion telefonica.",
        technologies=[],
        salary_min=22000,
        salary_max=22000,
        remote_type=RemoteType.ONSITE,
        location="Sevilla, Spain",
        requirements="Certificado de discapacidad igual o superior al 33%.",
        experience_min_years=None,
        experience_max_years=None,
    )

    result = ScoringEngine("engineering").score(job)

    assert result.score < 35
    assert any("backend" in reason.lower() for reason in result.negative)


def test_operations_profile_scores_administrative_offer_highly() -> None:
    job = _job(
        title="Auxiliar administrativo/a",
        description=(
            "Gestion documental, atencion al cliente, facturacion, compras y soporte "
            "administrativo con Excel, Word, Outlook y Office."
        ),
        technologies=[
            "Excel",
            "Word",
            "Outlook",
            "Office",
            "Facturacion",
            "Gestion documental",
        ],
        salary_min=18000,
        salary_max=22000,
        remote_type=RemoteType.ONSITE,
        location="Sevilla, Spain",
        requirements="Jornada continua de manana. 1 ano de experiencia.",
        experience_min_years=1,
        experience_max_years=1,
        salary_currency="EUR",
    )

    result = ScoringEngine("operations").score(job)

    assert result.score >= 80
    assert result.level == "excellent"
    assert any("administracion" in reason.lower() for reason in result.positive)


def test_operations_profile_rejects_java_developer_offer() -> None:
    job = _job(
        title="Java Backend Developer",
        description="Build Java Spring Boot APIs with AWS and Docker.",
        technologies=["Java", "Spring Boot", "AWS"],
        salary_min=30000,
        salary_max=35000,
        remote_type=RemoteType.REMOTE,
        location="Spain",
        requirements="2 years of experience",
        experience_min_years=2,
        experience_max_years=2,
        salary_currency="EUR",
    )

    result = ScoringEngine("operations").score(job)

    assert result.score < 35
    assert any("administracion" in reason.lower() for reason in result.negative)


def test_operations_profile_rejects_portuguese_language_requirement() -> None:
    job = _job(
        title="Administrativo/a - Portugu\u00e9s",
        description="Atencion al cliente, contabilidad, facturacion y gestion documental.",
        technologies=["Contabilidad", "Facturacion", "Gestion documental"],
        salary_min=18000,
        salary_max=22000,
        remote_type=RemoteType.ONSITE,
        location="Sevilla, Spain",
        requirements="Se requiere portugues alto y 2 anos de experiencia.",
        experience_min_years=2,
        experience_max_years=2,
        salary_currency="EUR",
    )

    result = ScoringEngine("operations").score(job)

    assert result.score < 35
    assert any("portugues" in reason.lower() for reason in result.negative)


def test_operations_profile_rejects_portuguese_job_text() -> None:
    job = _job(
        title="Estagi\u00e1rio(a) Contabilidade/ Administrativo",
        description=(
            "Licenciatura na area contabilistica. Conhecimentos de ingles, "
            "bom conhecimento de ferramentas informaticas e dinamismo."
        ),
        technologies=["Contabilidad", "Office"],
        salary_min=18000,
        salary_max=22000,
        remote_type=RemoteType.ONSITE,
        location="Almeria, Spain",
        requirements="No se requiere experiencia | jornada completa | contrato indefinido",
        experience_min_years=None,
        experience_max_years=None,
        salary_currency="EUR",
    )

    result = ScoringEngine("operations").score(job)

    assert result.score < 35
    assert any(
        "idioma" in reason.lower() or "portugues" in reason.lower()
        for reason in result.negative
    )


def test_operations_profile_rejects_non_supported_language_or_disability_certificate() -> None:
    job = _job(
        title="Recepcionista / Auxiliar Administrativa con franc\u00e9s alto",
        description=(
            "Atencion al cliente, gestion documental y archivo. "
            "Imprescindible certificado de discapacidad."
        ),
        technologies=["Gestion documental", "Atencion al cliente", "Office"],
        salary_min=18000,
        salary_max=22000,
        remote_type=RemoteType.ONSITE,
        location="Sevilla, Spain",
        requirements="Se requiere franc\u00e9s alto y certificado de discapacidad.",
        experience_min_years=1,
        experience_max_years=2,
        salary_currency="EUR",
    )

    result = ScoringEngine("operations").score(job)

    assert result.score < 35
    assert any("idioma" in reason.lower() for reason in result.negative)


def _job(
    *,
    title: str,
    description: str,
    technologies: list[str],
    salary_min: int | None,
    salary_max: int | None,
    remote_type: RemoteType,
    location: str,
    requirements: str = "1-2 years of experience",
    experience_min_years: float | None = 1,
    experience_max_years: float | None = 2,
    salary_currency: str | None = None,
) -> NormalizedJob:
    return NormalizedJob(
        source_job_id="test-job",
        company_name="Example",
        company_website=None,
        title=title,
        normalized_title=title.lower(),
        description=description,
        requirements=requirements,
        location=location,
        country="Spain",
        remote_type=remote_type,
        employment_type="full-time",
        experience_min_years=experience_min_years,
        experience_max_years=experience_max_years,
        salary_min=salary_min,
        salary_max=salary_max,
        salary_currency=salary_currency or ("EUR" if salary_min is not None else None),
        salary_period="annual" if salary_min is not None else None,
        salary_original_text=None,
        salary_unknown=salary_min is None,
        url="https://example.test/job",
        publication_date=datetime.now(UTC),
        expiration_date=None,
        technologies=technologies,
        raw_payload={},
        content_hash="hash",
        language="en",
    )
