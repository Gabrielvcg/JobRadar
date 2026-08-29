from __future__ import annotations

import hashlib
import re
import unicodedata
from html import unescape
from typing import Any

from bs4 import BeautifulSoup

from app.models.enums import RemoteType

EXPERIENCE_RANGE_RE = re.compile(
    r"(?P<min>\d+(?:[.,]\d+)?)\s*(?:-|–|—|to|a)\s*(?P<max>\d+(?:[.,]\d+)?)\s*"
    r"(?:years?|anos?|años?)",
    re.IGNORECASE,
)
EXPERIENCE_SINGLE_RE = re.compile(
    r"(?P<years>\d+(?:[.,]\d+)?)\+?\s*(?:years?|anos?|años?)",
    re.IGNORECASE,
)


def clean_html(value: str) -> str:
    soup = BeautifulSoup(value or "", "html.parser")
    text = soup.get_text(" ")
    return normalize_whitespace(unescape(text))


def normalize_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def normalize_title(title: str) -> str:
    cleaned = normalize_whitespace(clean_html(title))
    cleaned = re.sub(r"\s*[\[(].*?[\])]", "", cleaned)
    return cleaned.lower()


def detect_technologies(text: str, scoring_config: dict[str, Any]) -> list[str]:
    technologies_config = scoring_config.get("technologies", {})
    if not isinstance(technologies_config, dict):
        return []
    found: list[str] = []
    for group in ("high", "medium", "secondary"):
        entries = technologies_config.get(group, {})
        if not isinstance(entries, dict):
            continue
        for name, patterns in entries.items():
            if not isinstance(patterns, list):
                continue
            if any(re.search(str(pattern), text, re.IGNORECASE) for pattern in patterns):
                found.append(str(name))
    return found


def extract_experience_years(text: str) -> tuple[float | None, float | None]:
    range_match = EXPERIENCE_RANGE_RE.search(text)
    if range_match:
        return _to_float(range_match.group("min")), _to_float(range_match.group("max"))
    single_match = EXPERIENCE_SINGLE_RE.search(text)
    if single_match:
        years = _to_float(single_match.group("years"))
        return years, years
    return None, None


def detect_remote_type(text: str, fallback: RemoteType = RemoteType.UNKNOWN) -> RemoteType:
    text_lower = text.lower()
    if any(token in text_lower for token in ("remote", "remoto", "teletrabajo", "work from home")):
        return RemoteType.REMOTE
    if any(token in text_lower for token in ("hybrid", "hibrido", "híbrido")):
        return RemoteType.HYBRID
    if any(token in text_lower for token in ("onsite", "on-site", "presencial")):
        return RemoteType.ONSITE
    return fallback


def detect_language(text: str) -> str | None:
    lower = _fold_text(text)
    padded = f" {lower} "
    spanish_markers = (
        " el ",
        " la ",
        " de ",
        " para ",
        " con ",
        " experiencia ",
        " salario ",
        " gestion ",
        " administracion ",
    )
    english_markers = (" the ", " and ", " with ", " salary ", " experience ", " remote ")
    portuguese_markers = (
        " com ",
        " experiencia ",
        " salario ",
        " emprego ",
        " trabalho ",
        " estagiario",
        " estagiaria",
        " contabilidade ",
        " escolaridade ",
        " conhecimentos ",
        " ferramentas ",
        " contabilistica ",
        " e/ou ",
    )
    german_markers = (
        " der ",
        " die ",
        " und ",
        " mit ",
        " fur ",
        " zum ",
        " aufgaben ",
        " erfahrung ",
        " bewerbung ",
        " gehalt ",
        " m/w/d",
    )
    spanish_score = sum(marker in padded for marker in spanish_markers)
    english_score = sum(marker in padded for marker in english_markers)
    portuguese_score = sum(marker in padded for marker in portuguese_markers)
    german_score = sum(marker in padded for marker in german_markers)
    if spanish_score == english_score == portuguese_score == german_score == 0:
        return None
    if german_score > max(spanish_score, english_score, portuguese_score):
        return "de"
    if portuguese_score > max(spanish_score, english_score):
        return "pt"
    return "es" if spanish_score > english_score else "en"


def content_hash(company: str, title: str, location: str | None, description: str) -> str:
    payload = "|".join(
        [
            normalize_whitespace(company).lower(),
            normalize_whitespace(title).lower(),
            normalize_whitespace(location or "").lower(),
            normalize_whitespace(description).lower(),
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def canonical_url(url: str | None) -> str | None:
    if not url:
        return None
    text = url.strip()
    if not text:
        return None
    return text.split("#", 1)[0].rstrip("/")


def _to_float(value: str) -> float | None:
    try:
        return float(value.replace(",", "."))
    except ValueError:
        return None


def _fold_text(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.lower())
    return "".join(character for character in decomposed if not unicodedata.combining(character))
