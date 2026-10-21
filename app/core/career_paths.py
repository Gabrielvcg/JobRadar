"""Conservative recognition of the engineering profile's adjacent career paths."""

from __future__ import annotations

import re

from app.scoring.evidence import development_evidence, operations_only


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
    return bool(development_evidence(text)) and not operations_only(title, text) and any(
        re.search(role, title, re.IGNORECASE) and re.search(stack, text, re.IGNORECASE)
        for role, stack in paths
    )
