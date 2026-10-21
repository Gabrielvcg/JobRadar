"""Incremental engineering policy built on the existing configurable scoring rules."""

from __future__ import annotations

import re
from dataclasses import asdict, replace
from datetime import UTC, date, datetime
from typing import TYPE_CHECKING, Any

from app.core.availability import current_verification
from app.core.experience import professional_months
from app.scoring.engine import ScoreResult
from app.scoring.evidence import (
    active_clauses,
    binding_experience,
    clauses,
    development_evidence,
    experience_requirements,
    fold,
    operations_only,
    requirement_kind,
)
from app.scoring.geography import assess_location
from app.scoring.text import detect_technologies
from app.services.normalizer import NormalizedJob

if TYPE_CHECKING:
    from app.scoring.engine import ScoringEngine


def score_career(engine: ScoringEngine, job: NormalizedJob, today: date) -> ScoreResult:
    profile = engine.profile_config["profile"]
    policy = profile["career"]
    months = professional_months(str(policy["professional_start_month"]), today)
    years = months / 12
    positive: list[str] = []
    negative: list[str] = []
    uncertain: list[str] = []
    blockers: list[str] = []
    text = f"{job.description}\n{job.requirements or ''}"
    evidence_text = "\n".join(active_clauses(f"{job.title}\n{text}"))
    technologies = detect_technologies(evidence_text, engine.scoring_config)
    # Do not feed normalized tags back into matching: they can include negated stack.
    evidence_job = replace(
        job,
        description=evidence_text,
        requirements=None,
        technologies=technologies,
        normalized_title=job.title.lower(),
    )
    role = engine._role_fit(evidence_job, positive)
    development = development_evidence(text)
    transition = engine._matches_career_transition(evidence_job)
    primary = bool(set(technologies) & {"Java", "Spring Boot"})
    backend = bool(
        re.search(r"\b(backend|back.end|software|java|spring|desarroll\w*)\b", fold(job.title))
    )
    java_work = bool(re.search(r"\b(java|spring|backend|back.end)\b", fold(job.title))) or any(
        re.search(r"\b(java|spring)\b", fold(clause)) for clause in development
    )
    aligned = (primary and backend and java_work) or transition
    if re.search(
        r"\b(ai coding tasks|coding evaluator|ai trainer|data annotator)\b", fold(job.title)
    ):
        aligned = False
    if not aligned:
        negative.append(
            "No hay encaje suficiente con backend Java/Spring o desarrollo AppSec/cloud"
        )
        blockers.append("role_mismatch")
    if operations_only(job.title, text):
        negative.append(
            "Puesto principalmente de soporte, helpdesk u operaciones sin desarrollo demostrado"
        )
        blockers.append("operations_only")
    professional = set(policy.get("professional_technologies", []))
    project = set(policy.get("project_technologies", []))
    tech_points = sum(
        4 if tech in professional else 1 if tech in project else 0 for tech in technologies
    )
    # Adjacent security skills are knowledge, not demonstrated employment in security.
    if transition:
        tech_points += min(6, len(set(technologies) - professional - project))
    tech_points = min(30, tech_points)
    if technologies:
        positive.append(f"Stack activo en la oferta: {', '.join(technologies[:10])}")
    engine._disability_focus_score(evidence_job, positive)
    if set(technologies) & project:
        uncertain.append(
            "Cloud/IaC de proyectos o certificaciones no equivale a experiencia profesional"
        )

    experience = experience_requirements(text)
    binding = binding_experience(experience)
    # Structured fields are a fallback, never override classified desirable requirements.
    if not experience and job.experience_min_years is not None:
        uncertain.append("Experiencia estructurada sin contexto verificable; confirmar requisito")
    exp_points = 14
    gap = 0.0
    if binding:
        gap = max(0, binding.minimum - years)
        exp_points = (
            25
            if gap == 0
            else 23
            if gap <= 1
            else 19
            if gap <= 2
            else 12
            if gap <= 3
            else 6
            if gap <= 4
            else 0
        )
        target = (
            f"{binding.minimum:g}-{binding.maximum:g}"
            if binding.minimum != binding.maximum
            else f"{binding.minimum:g}"
        )
        reason = (
            f"Experiencia {binding.kind}: {target} anos; "
            f"trayectoria profesional calculada: {months} meses"
        )
        (negative if gap > 0 else positive).append(reason)
    else:
        uncertain.append("Experiencia obligatoria no especificada; no se presupone cumplida")
    if any(item.kind == "desirable" for item in experience):
        positive.append("Experiencia deseable separada de los requisitos obligatorios")

    english_points = 8
    english = "not_specified"
    for clause in clauses(text):
        lower = fold(clause)
        if not re.search(r"\b(english|ingles)\b", lower):
            continue
        if requirement_kind(clause) == "desirable":
            continue
        if re.search(r"\b(c1|c2|fluent|native|bilingual|fluido|bilingue|nativo)\b", lower):
            english_points, english = 2, "above_certified_b2"
            negative.append(
                "Ingles exigido superior al B2 certificado; C1 es un objetivo pendiente"
            )
        elif re.search(r"\bb[12]\b|intermediate|intermedio", lower):
            english_points, english = 10, "compatible_b2"

    required_unknown = []
    for clause in active_clauses(text):
        if requirement_kind(clause) != "mandatory":
            continue
        lower = fold(clause)
        if re.search(r"\b(java|spring)\b.*\bor\b|\bor\b.*\b(java|spring)\b", lower):
            continue
        if re.search(r"(?<!\w)(golang|ruby|rails|rust|c\+\+|\.net|c#|swift)(?!\w)", lower):
            required_unknown.append(clause[:300])
    if required_unknown:
        negative.append(
            "Stack obligatorio alejado de la experiencia demostrada; revisar requisitos"
        )
        blockers.append("mandatory_stack_mismatch")

    unsupported = []
    languages = r"\b(french|frances|german|aleman|portuguese|portugues|dutch|neerlandes)\b"
    for clause in [job.title, *clauses(text)]:
        lower = fold(clause)
        if requirement_kind(clause) == "desirable":
            continue
        if re.search(languages, lower) and (
            clause == job.title
            or requirement_kind(clause) == "mandatory"
            or re.search(r"\b(b2|c1|c2|fluent|alto|fluido|bilingue|native)\b", lower)
        ):
            unsupported.append(clause[:200])
    if unsupported:
        negative.append("Idioma obligatorio fuera del perfil espanol/ingles certificado")
        blockers.append("unsupported_language")

    responsibility_points = 10 if development else 3
    if not development:
        uncertain.append("Descripcion sin responsabilidades concretas de desarrollo verificables")
    fit = max(0, min(100, role + tech_points + exp_points + english_points + responsibility_points))
    growth, growth_reasons = _growth(text)
    positive.extend(growth_reasons)
    location = assess_location(
        job.location,
        job.country,
        job.remote_type,
        text,
        list(profile.get("location", {}).get("preferred_locations", ["Sevilla"])),
    )
    (
        positive
        if location.status == "compatible"
        else negative
        if location.status == "incompatible"
        else uncertain
    ).append(location.reason)
    if location.status == "incompatible":
        blockers.append("location_incompatible")

    salary_status, salary_points, salary_reason = _salary(engine, job)
    (
        negative
        if salary_status == "below_minimum"
        else uncertain
        if salary_status in {"unknown", "published_not_comparable", "overlapping_minimum"}
        else positive
    ).append(salary_reason)
    if salary_status == "below_minimum":
        blockers.append("salary_below_minimum")

    availability = current_verification(job.raw_payload, job.url)
    if availability["state"] == "closed":
        blockers.append("listing_closed")
        negative.append("La pagina confirma que la oferta ya no acepta candidaturas")
    elif availability["state"] == "active":
        positive.append("Pagina accesible con un control habilitado para presentar candidatura")
    else:
        uncertain.append(
            "Solicitud sin verificar; una ingesta reciente no demuestra que siga abierta"
        )

    freshness_points = 100
    freshness = "undated"
    if job.expiration_date and _day(job.expiration_date) < today:
        freshness, freshness_points = "expired", 0
        blockers.append("expired")
        negative.append("Oferta caducada segun su fecha de expiracion")
    elif job.publication_date:
        age = (today - _day(job.publication_date)).days
        freshness = "fresh" if age <= 45 else "aging" if age <= 90 else "stale"
        freshness_points = 100 if age <= 45 else 70 if age <= 90 else 30
        if age < 0:
            freshness, freshness_points = "future_date", 50
            uncertain.append("Fecha de publicacion futura; confirmar vigencia")
        elif age > 45:
            negative.append(f"Publicada hace {age} dias; confirmar vigencia")
    else:
        freshness_points = 70
        uncertain.append("Vigencia desconocida: no publica fecha")

    viability = round(
        0.35 * location.points
        + 0.25 * salary_points
        + 0.2 * freshness_points
        + 0.2 * (100 if development else 50)
    )
    viability -= round(min(35, gap * (10 if binding and binding.kind == "mandatory" else 7)))
    if english == "above_certified_b2":
        viability -= 15
    advanced_title = re.search(
        r"\b(senior|sr|staff|principal|lead|architect|arquitect\w*|head of|manager)\b",
        fold(job.title),
    )
    advanced_duties = re.search(
        r"\b(own|lead|define|liderar|definir)\w*\s+(?:the\s+)?(?:company.wide|cross.team|"
        r"organization.wide|technical strategy|estrategia tecnica|arquitectura corporativa)\b",
        fold(text),
    )
    future = bool(
        advanced_title or advanced_duties or (binding and binding.minimum > max(5, years + 2))
    )
    category = (
        "C" if future else "A" if primary and backend else "B" if transition else "unclassified"
    )
    if future:
        negative.append(
            "Referencia senior/arquitectura futura; la antiguedad por si sola no acredita seniority"
        )
        viability = min(viability, 55)
    if advanced_duties:
        negative.append("Responsabilidades de liderazgo transversal evidencian seniority real")
    if binding and binding.kind == "mandatory" and gap > 2:
        viability = min(viability, 45)
    viability = max(0, min(100, viability))
    # Core fit and feasibility dominate. Growth cannot overcome an eliminating condition.
    weights = engine.scoring_config.get(
        "career_weights", {"professional_fit": 0.65, "growth": 0.1, "viability": 0.25}
    )
    score = round(
        fit * weights["professional_fit"]
        + growth * weights["growth"]
        + viability * weights["viability"]
    )
    if future:
        score = min(score, 59)
    elif gap > 3:
        score = min(score, 49)
    elif gap > 2 and growth < 60:
        score = min(score, 59)
    if not aligned or blockers:
        score = min(score, 34)
    if not aligned and not technologies:
        score = min(score, 19)
    if operations_only(job.title, text):
        score = min(score, 19)
    radar = "excluded" if blockers else "strategic" if future else "current"
    if not development and len(text.split()) < 20:
        score = min(score, 69)
    score = max(0, min(100, score))
    assessment: dict[str, Any] = {
        "version": engine.policy_version,
        "evaluated_on": today.isoformat(),
        "professional_months": months,
        "category": category,
        "radar": radar,
        "professional_fit": fit,
        "growth": growth,
        "viability": viability,
        "experience_requirements": [asdict(item) for item in experience],
        "location_status": location.status,
        "remote_scope": location.scope,
        "salary_status": salary_status,
        "salary_evidence": "published" if not job.salary_unknown else "unknown",
        "english_requirement": english,
        "freshness": freshness,
        "availability": availability,
        "blockers": blockers,
        "uncertainties": uncertain,
        "development_evidence": development[:4],
        "mandatory_stack_gaps": required_unknown,
        "unsupported_language_evidence": unsupported,
        "heuristic_only": True,
    }
    positive.insert(
        0,
        f"Encaje profesional {fit}/100; crecimiento {growth}/100; "
        f"viabilidad {viability}/100 (heuristica, no probabilidad)",
    )
    negative.extend(uncertain)
    return ScoreResult(score, engine._level(score), positive, negative, assessment)


def _growth(text: str) -> tuple[int, list[str]]:
    evidence = " ".join(development_evidence(text))
    rules = (
        (
            r"\b(?:design|disen\w*|architecture|arquitectura)\b",
            20,
            "Diseno de sistemas en las responsabilidades",
        ),
        (
            r"\b(?:distributed|distribuid\w*|messaging|mensajeria|kafka|sqs|rabbitmq)\b",
            20,
            "Desarrollo de sistemas distribuidos o mensajeria",
        ),
        (r"\b(?:aws|lambda|dynamodb|s3)\b", 20, "Desarrollo de servicios sobre AWS"),
        (
            r"\b(?:terraform|infrastructure as code|infraestructura como codigo)\b",
            15,
            "Automatizacion de infraestructura como codigo",
        ),
        (
            r"\b(?:resilien\w*|scalab\w*|escalab\w*|concurren\w*|security|seguridad)\b",
            15,
            "Ingenieria de resiliencia, escalabilidad o seguridad",
        ),
    )
    reasons, points = [], 0
    for pattern, value, reason in rules:
        if re.search(pattern, fold(evidence)):
            points += value
            reasons.append(reason)
    if re.search(
        r"\b(mentorship|mentoring|mentoria|career progression|plan de carrera)\b", fold(text)
    ):
        points += 10
        reasons.append("Mentoria o progresion explicitada")
    return min(100, points), reasons


def _salary(engine: ScoringEngine, job: NormalizedJob) -> tuple[str, int, str]:
    if job.salary_unknown or (job.salary_min is None and job.salary_max is None):
        return "unknown", 65, "Salario desconocido; se conserva sin estimaciones inventadas"
    if job.salary_currency != "EUR" or job.salary_period not in {None, "annual", "monthly"}:
        return (
            "published_not_comparable",
            65,
            "Salario publicado; conversion de moneda o tarifa no verificada",
        )
    minimum = int(engine.salary_config["minimum_annual_eur"])
    upper = job.salary_max if job.salary_max is not None else job.salary_min
    assert upper is not None
    if upper < minimum:
        return "below_minimum", 0, f"Salario publicado inferior al minimo de cambio: {minimum} EUR"
    if job.salary_min is None or job.salary_min < minimum:
        return (
            "overlapping_minimum",
            60,
            f"El salario publicado no garantiza el minimo de {minimum} EUR; confirmar oferta final",
        )
    if job.salary_min >= int(engine.salary_config["target_min_annual_eur"]):
        return (
            "target_or_above",
            100,
            "Salario publicado en rango preferido o superior; "
            "sin inferir probabilidad de contratacion",
        )
    return "minimum_met", 85, "Salario publicado cumple el minimo para cambiar de empresa"


def _day(value: datetime) -> date:
    return (value.replace(tzinfo=UTC) if value.tzinfo is None else value).date()
