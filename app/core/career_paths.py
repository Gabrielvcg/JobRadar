"""Conservative recognition of the engineering profile's adjacent career paths."""

from __future__ import annotations

import re

from app.scoring.evidence import development_evidence, fold, operations_only


def matches_career_transition(title: str, text: str) -> bool:
    """Require a relevant job title and concrete technical evidence, not just 'cloud'."""
    paths = (
        (
            r"\b(?:devops|devsecops|sre|site reliability|platform engineer|cloud engineer|"
            r"ingenier[oa] (?:de )?(?:cloud|plataforma))\b",
            r"\b(?:aws|azure|gcp|terraform|docker|kubernetes|linux|ansible|ci/cd)\b",
        ),
        (
            r"\b(?:appsec|application security|cloud security|seguridad de aplicaciones)\b",
            r"\b(?:owasp|sast|dast|iam|sdlc|threat model\w*|aws|azure|gcp)\b",
        ),
    )
    infrastructure_role = re.search(paths[0][0], title, re.IGNORECASE)
    if infrastructure_role and not any(
        re.search(
            r"\b(build|develop|implement|automate|write|desarroll\w*|automatiz\w*)\b", fold(c)
        )
        and re.search(
            r"\b(apis?|tools?|software|services?|pipelines?|code|herramientas?|servicios?)\b",
            fold(c),
        )
        for c in development_evidence(text)
    ):
        return False
    return (
        bool(development_evidence(text))
        and not operations_only(title, text)
        and any(
            re.search(role, title, re.IGNORECASE) and re.search(stack, text, re.IGNORECASE)
            for role, stack in paths
        )
    )
