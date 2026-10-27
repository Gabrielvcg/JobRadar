"""Evidence about the work performed, separate from technology overlap."""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass

from app.scoring.evidence import ExperienceRequirement, clauses, fold, requirement_kind


@dataclass(frozen=True)
class WorkAlignment:
    focus: str
    points: int
    software: list[str]
    operations: list[str]
    specialist_gaps: list[str]
    independent_experience: list[str]


def requirement_clauses(text: str) -> list[tuple[str, str]]:
    """Keep requirement headings attached to their following list items."""
    context = "indicative"
    result = []
    for clause in clauses(text):
        value = fold(clause).strip(" :¿")
        if len(value) < 100:
            if re.fullmatch(
                r"(?:requirements?|qualifications?|minimum qualifications?|skills required|"
                r"must (?:to )?have skills|para hacer match\.*|"
                r"what (?:we.re looking for|you.ll bring|you bring)|"
                r"requisitos(?: minimos| imprescindibles)?|que buscamos|buscamos"
                r"(?: experiencia en)?|experiencia (?:en|con))", value,
            ):
                context = "mandatory"
                continue
            if re.fullmatch(
                r"nice to have(?: skills)?|desirable|bonus(?: points)?|valorable|deseable", value,
            ):
                context = "desirable"
                continue
            if re.fullmatch(
                r"responsibilities|responsabilidades|funciones|conditions|condiciones|"
                r"benefits|beneficios|what we offer|que ofrecemos|compania", value,
            ):
                context = "indicative"
        kind = requirement_kind(clause)
        result.append((clause, context if kind == "indicative" else kind))
    return result


def analyze_work(
    title: str, text: str, professional: set[str], experience: Sequence[ExperienceRequirement],
) -> WorkAlignment:
    name = fold(title)
    software, operations = [], []
    dominant_operations = []
    section = "duties"
    for clause in clauses(text):
        value = fold(clause)
        declared_operations = re.search(
            r"\b(?:orientad\w*|enfocad\w*|centrad\w*)\s+"
            r"(?:principalmente|mayoritariamente)\s+(?:a|en)\s+(?:(?:las?|el|los)\s+)?"
            r"(?:operacion(?:es)?|soporte|monitorizacion|administracion de sistemas)\b",
            value,
        )
        if declared_operations and not re.search(
            r"\bno(?:\s+esta)?\s*$", value[:declared_operations.start()],
        ):
            dominant_operations.append(clause[:400])
            operations.append(clause[:400])
        if len(value) < 100 and re.fullmatch(
            r"requirements?|qualifications?|skills required|requisitos(?: minimos)?|"
            r"buscamos(?: experiencia en)?|what we.re looking for|benefits|beneficios|"
            r"que ofrecemos|what we offer|about (?:the company|us)", value.strip(" :¿"),
        ):
            section = "other"
        elif len(value) < 100 and re.fullmatch(
            r"(?:key )?responsibilities|responsabilidades|funciones(?: principales)?|"
            r"que haras|what you.ll (?:do|be doing)|about the role", value.strip(" :¿"),
        ):
            section = "duties"
        product = bool(
            re.search(
                r"\b(?:build(?:s|ing)?|develop(?:s|ed|ing)?|design(?:s|ed|ing)?|"
                r"implement(?:s|ed|ing)?|writ(?:e|es|ing)|cod(?:e|es|ing)|"
                r"creat(?:e|es|ing)|crear|desarroll(?:ar|a|amos|ando|o)|disen\w*|"
                r"implementar|programar|constru\w*)\b", value,
            )
            and re.search(
                r"\b(?:apis?|microservices?|backend|back.end|software|applications?|"
                r"features?|functionality|sdks?|libraries|developer tools?|platform apis?|"
                r"aplicaciones?|funcionalidades|microservicios?|servicios backend|"
                r"distributed services|threat model\w*)\b", value,
            )
        )
        if re.search(r"\b(?:java|backend|software)\b", name) and re.search(
            r"\b(?:desarrollos? de proyectos|rol de desarrollador|rol de analista programador)",
            value,
        ):
            product = True
        if re.search(r"\b(?:appsec|application security|devsecops)\b", name) and re.search(
            r"\b(?:review|design|implement)\b.*\b(?:apis?|threat model\w*|sdlc)\b", value,
        ):
            product = True
        operation = bool(
            len(value.split()) >= 6
            and re.search(
                r"\b(?:monitor|operat|administ|provision|support|maintain|manage|deploy|"
                r"troubleshoot|manteni|gestion|soport)\w*\b", value,
            )
            and re.search(
                r"\b(?:infrastructure|infraestructura|clusters?|servers?|servidores|"
                r"network|networks|ci/cd|pipelines?|linux|monitoring|kubernetes)\b", value,
            )
        )
        if section == "duties" and product:
            software.append(clause[:400])
        if section == "duties" and operation:
            operations.append(clause[:400])
    if dominant_operations:
        # Explicit primary duties outrank incidental corrective Java development.
        # Keep software evidence: this is predominance, not absence of coding.
        focus, points = "operations", 15
    elif re.search(r"\b(?:soc|helpdesk|sysadmin|system administrator|pentester)\b", name):
        focus, points = "operations", 10
    elif re.search(r"\b(?:qa|sdet|test automation|software test)\b", name):
        focus, points = "quality_assurance", 30
    elif re.search(r"\b(?:ai trainer|coding tasks|coding evaluator|data annotator)\b", name):
        focus, points = "ai_evaluation", 0
    elif not software and re.search(
        r"\b(?:engineering manager|product owner|head of|director)\b", name,
    ):
        focus, points = "management", 10
    elif re.search(r"\b(?:frontend|front.end)\b", name) and not re.search(
        r"\b(?:backend|back.end|full.stack)\b", name,
    ):
        focus, points = "frontend", 25
    elif software and re.search(r"\b(?:backend|back.end|java|spring|software|desarroll)\w*", name):
        focus, points = "backend", 100
    elif software and re.search(r"\b(?:appsec|application security|devsecops)\b", name):
        focus, points = "application_security", 60
    elif software:
        focus, points = "software_platform", 75
    elif operations:
        focus, points = "operations", 15
    else:
        focus, points = "unknown", 40

    gaps = []
    for clause, kind in requirement_clauses(text):
        value = fold(clause)
        if kind == "desirable":
            continue
        required = kind == "mandatory" or bool(re.search(
            r"\b(?:experience|experiencia|conocimientos|dominio|uso de metodologia)\b", value,
        ))
        for technology in ("Angular", "React", "Liferay", "Kotlin", "Python", "AWS", "Azure",
                           "Terraform", "Kubernetes", "OpenShift", "Kafka", "SDD"):
            if (
                required and technology not in professional
                and re.search(rf"\b{technology.lower()}\b", value)
                and (technology in {"Angular", "React", "Liferay", "Kotlin", "Python", "SDD"}
                     or re.search(r"\b(?:experience|experiencia|dominio|avanzad\w*)\b", value))
                and not re.search(
                    rf"\b(?:java|spring(?: boot)?)\s*(?:,\s*)?(?:or|and/or|y/o|o)\s*"
                    rf"{technology.lower()}\b|\b{technology.lower()}\s*"
                    r"(?:or|and/or|y/o|o)\s*(?:java|spring(?: boot)?)\b", value,
                )
                and not (re.search(r"\bjava\b", value) and re.search(
                    r"\b(?:one or more|at least one|such as)\b", value,
                ))
            ):
                gaps.append(f"{technology}: {clause[:220]}")
    independent = []
    for item in experience:
        minimum = getattr(item, "minimum", 0)
        evidence = getattr(item, "evidence", "")
        if minimum <= 0 or getattr(item, "kind", "") == "desirable":
            continue
        domains = {
            "Angular": r"frontend|front.end|angular|react",
            "AWS": r"\baws\b",
            "Kotlin": r"\bkotlin\b",
            "Python": r"\bpython\b",
            "DevOps": r"\b(?:devops|sre|site reliability)\b",
        }
        if any(tech not in professional and re.search(pattern, fold(evidence))
               for tech, pattern in domains.items()):
            independent.append(evidence[:300])
    return WorkAlignment(focus, points, software, operations,
                         list(dict.fromkeys(gaps)), list(dict.fromkeys(independent)))


def recommendation(
    *, blockers: list[str], future: bool, work: WorkAlignment, location: str,
    availability: str, experience_gap: float, english: str,
) -> tuple[str, str]:
    if blockers:
        return "D", "Incompatibilidad acreditada: " + ", ".join(blockers)
    if future:
        return "C", "Referencia tecnica futura; no priorizar candidatura actual"
    if work.focus == "unknown" or not work.software:
        return "U", "Responsabilidades de desarrollo insuficientemente acreditadas"
    if location != "compatible":
        return "U", "Falta confirmar ubicacion o contratacion desde Sevilla/Espana"
    critical = any(gap.startswith(("Angular:", "React:", "Liferay:"))
                   for gap in work.specialist_gaps)
    if critical or work.independent_experience:
        return "U", "Falta acreditar un requisito profesional especializado"
    if availability != "active":
        return "U", "Falta confirmar una via actual de candidatura"
    if (work.focus == "backend" and experience_gap <= 1
            and not work.specialist_gaps and english != "above_certified_b2"):
        return "A", "Backend alineado, ubicacion compatible y via de solicitud comprobada"
    return "B", "Candidatura ambiciosa: revisar brechas de experiencia o especializacion"
