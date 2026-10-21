"""Residence compatibility is separate from the remote label."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.models.enums import RemoteType
from app.scoring.evidence import fold


@dataclass(frozen=True)
class LocationAssessment:
    status: str
    scope: str
    points: int
    reason: str


def assess_location(
    location: str | None,
    country: str | None,
    remote_type: RemoteType,
    description: str,
    local_terms: list[str],
) -> LocationAssessment:
    # Specific location wins over a broad country label inferred by a portal.
    place = fold(location or country or "")
    text = fold(description)
    if re.search(
        r"\b(?:not (?:available|open) (?:in|to)|except|excluding|no disponible en)\s+spain\b", text
    ):
        return LocationAssessment("incompatible", "restricted", 0, "Excluye residencia en Espana")
    restricted = re.search(
        r"\b(?:must (?:be (?:based|located)|reside|live)|residen\w* obligatori\w*|"
        r"only (?:candidates|applicants|residents) (?:in|from))\s+(?:in\s+)?"
        r"(germany|france|poland|uk|united kingdom|us|usa|united states|portugal)\b",
        text,
    )
    if restricted:
        return LocationAssessment(
            "incompatible",
            "restricted",
            0,
            f"Residencia obligatoria fuera de Espana: {restricted.group(1)}",
        )
    regional = re.search(
        r"\b(?:resida[ns]?|residencia obligatoria|debes? residir)\s+en\s+"
        r"(galicia|madrid|barcelona|cataluna|pais vasco|valencia|zaragoza|bilbao)\b",
        text,
    )
    if regional:
        return LocationAssessment(
            "incompatible",
            "regional_residence",
            0,
            f"Exige residencia fuera de Sevilla: {regional.group(1)}",
        )
    local = any(re.search(rf"(?<!\w){re.escape(fold(term))}(?!\w)", place) for term in local_terms)
    remote_spain = re.search(
        r"\b(?:remote (?:from|within|in)|remoto (?:desde|en)|teletrabajo (?:desde|en))"
        r"\s+(?:all of\s+)?"
        r"(?:spain|espana)\b|\b(?:spain|espana) (?:accepted|eligible)\b",
        text,
    )
    if remote_type == RemoteType.REMOTE:
        if re.search(r"\b(spain|espana)\b", place) or remote_spain:
            return LocationAssessment(
                "compatible",
                "spain",
                100,
                "Remoto con Espana incluida; confirmar condiciones contractuales",
            )
        if re.search(r"\b(worldwide|anywhere|global|world)\b", place):
            return LocationAssessment(
                "uncertain",
                "worldwide",
                70,
                "Remoto mundial; elegibilidad y contrato desde Espana por confirmar",
            )
        if re.search(r"\b(europe|european union|eu|emea)\b", place):
            return LocationAssessment(
                "uncertain",
                "europe",
                65,
                "Remoto europeo; Espana no esta confirmada explicitamente",
            )
        if not place.strip() or place.strip() in {"remote", "remoto"}:
            return LocationAssessment(
                "uncertain", "unknown", 45, "Remoto sin paises elegibles; confirmar Espana"
            )
        return LocationAssessment(
            "incompatible",
            "country_restricted",
            0,
            "Remoto limitado a otra ubicacion; no presupone residencia en Espana",
        )
    if local:
        return LocationAssessment(
            "compatible", "local", 90, "Presencial o hibrido compatible en Sevilla"
        )
    if remote_spain and remote_type == RemoteType.UNKNOWN:
        return LocationAssessment(
            "uncertain", "spain", 65, "Teletrabajo desde Espana pendiente de confirmar modalidad"
        )
    if place.strip():
        return LocationAssessment(
            "incompatible",
            "relocation",
            0,
            "Requiere presencia fuera de Sevilla; no se presupone traslado",
        )
    return LocationAssessment("uncertain", "unknown", 40, "Ubicacion y modalidad sin confirmar")
