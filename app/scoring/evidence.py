"""Small, auditable evidence rules. Unknown requirements stay unknown."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass


def fold(value: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFKD", value.lower()) if not unicodedata.combining(c)
    )


def clauses(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"[\n;!?•]+|(?<!\d)\.(?=\s|$)", text) if s.strip()]


def requirement_kind(text: str) -> str:
    text = fold(text)
    if re.search(
        r"\b(preferred|desirable|nice to have|bonus|valued|deseable|valorable|idealmente)\b", text
    ):
        return "desirable"
    if re.search(
        r"\b(required|must|minimum|at least|mandatory|essential|imprescindible|"
        r"obligatori\w*|requisito|minim[oa]|al menos|se requiere)\b",
        text,
    ):
        return "mandatory"
    return "indicative"


@dataclass(frozen=True)
class ExperienceRequirement:
    minimum: float
    maximum: float
    kind: str
    evidence: str


EXPERIENCE = re.compile(
    r"(?<![\d.])(?P<min>\d+(?:[.,]\d+)?)\s*(?:\+|or more)?\s*"
    r"(?:(?:-|–|—|to|a)\s*(?P<max>\d+(?:[.,]\d+)?)\s*)?"
    r"(?:years?|anos?)\b",
    re.IGNORECASE,
)


def experience_requirements(text: str) -> list[ExperienceRequirement]:
    found = []
    for clause in clauses(text):
        normalized = fold(clause)
        for match in EXPERIENCE.finditer(normalized):
            context = normalized[max(0, match.start() - 65) : match.end() + 100]
            if not re.search(
                r"\b(experience|experiencia|java|spring|backend|development|"
                r"desarrollo|engineering|aws|python|kubernetes|terraform)\b",
                context,
            ):
                continue
            if re.search(
                r"\b(our company|company has|founded|empresa tiene|fundad\w*|"
                r"entorno con|anos de trayectoria|years in business|"
                r"public sector|sector publico)\b",
                normalized,
            ) and not re.search(r"\b(you have|you bring|candidat\w*|tienes|tengas)\b", normalized):
                continue
            minimum = float(match.group("min").replace(",", "."))
            maximum = float((match.group("max") or match.group("min")).replace(",", "."))
            prefix = normalized[max(0, match.start() - 20) : match.start()]
            if not match.group("max") and re.search(
                r"\b(?:up to|at most|hasta|maximo(?: de)?)\s*$", prefix
            ):
                minimum = 0
            if minimum > maximum or maximum > 45:
                continue
            found.append(
                ExperienceRequirement(minimum, maximum, requirement_kind(clause), clause[:400])
            )
    return found


def binding_experience(items: list[ExperienceRequirement]) -> ExperienceRequirement | None:
    mandatory = [item for item in items if item.kind == "mandatory"]
    indicative = [item for item in items if item.kind == "indicative"]
    return max(mandatory or indicative, key=lambda item: item.minimum, default=None)


def active_clauses(text: str) -> list[str]:
    """Ignore explicitly negated/retired stack; retain original evidence for explanations."""
    return [
        c
        for c in clauses(text)
        if not re.search(
            r"\b(no longer|do not use|don't use|not required|not using|no usamos|no utilizamos|"
            r"no se requiere|sin experiencia en|migrat\w* away from|migramos desde)\b",
            fold(c),
        )
    ]


DEVELOPMENT = (
    r"\b(build|develop|design|implement|code|coding|programming|automate|review|"
    r"desarroll\w*|disen\w*|implement\w*|program\w*|automatiz\w*|revis\w*)\b"
)
ARTIFACTS = (
    r"\b(apis?|services?|systems?|software|applications?|pipelines?|tools?|platforms?|"
    r"automation|sdlc|threat model\w*|servicios?|sistemas?|aplicaciones?|herramientas?)\b"
)


def development_evidence(text: str) -> list[str]:
    return [
        c
        for c in active_clauses(text)
        if re.search(DEVELOPMENT, fold(c)) and re.search(ARTIFACTS, fold(c))
    ]


def operations_only(title: str, text: str) -> bool:
    title = fold(title)
    if re.search(
        r"\b(helpdesk|sysadmin|system administrator|soporte|monitoring operator|soc l1)\b", title
    ):
        return not development_evidence(text)
    return bool(
        re.search(
            r"\b(exclusively|primarily|mainly|principalmente|exclusivamente)\s+"
            r"(?:focused on\s+)?(?:monitoring|support|maintenance|"
            r"monitorizacion|soporte|mantenimiento)\b",
            fold(text),
        )
    ) and not development_evidence(text)
