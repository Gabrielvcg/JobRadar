from __future__ import annotations

import hashlib
import re
import unicodedata
from html import unescape
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from bs4 import BeautifulSoup

from app.models.enums import RemoteType
from app.scoring.evidence import binding_experience, experience_requirements

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
    soup = BeautifulSoup(unescape(value or ""), "html.parser")
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
    requirement = binding_experience(experience_requirements(text))
    if requirement:
        return requirement.minimum, requirement.maximum
    return None, None


def detect_remote_type(
    text: str,
    fallback: RemoteType = RemoteType.UNKNOWN,
    *,
    location: str | None = None,
) -> RemoteType:
    text_lower = text.lower()
    place = (location or "").lower()
    if re.search(r"\b(hybrid|hibrido|híbrido)\b", place):
        return RemoteType.HYBRID
    if re.search(r"\b(onsite|on-site|presencial)\b", place):
        return RemoteType.ONSITE
    if re.search(r"\b(no remote|not remote|sin teletrabajo|no teletrabajo)\b", text_lower):
        return RemoteType.ONSITE
    # Hybrid/onsite requirements outrank incidental remote benefits.
    if any(token in text_lower for token in ("hybrid", "hibrido", "híbrido")):
        return RemoteType.HYBRID
    # Interviews and occasional gatherings do not establish mandatory office work.
    mode_text = re.sub(
        r"\b(?:onsite|on-site)\s+(?:interviews?|events?|gatherings?|meetings?)\b",
        "",
        text_lower,
    )
    office_required = re.search(
        r"\b(?:must|required to|expected to)\s+(?:work|attend|be)\b[^.!?]{0,60}"
        r"\b(?:office|onsite|on-site)\b|\b\d+\s+days? (?:a|per) week\b[^.!?]{0,40}\boffice\b",
        mode_text,
    )
    if office_required:
        return RemoteType.HYBRID if re.search(r"\d+\s+days?", mode_text) else RemoteType.ONSITE
    if fallback == RemoteType.REMOTE:
        return RemoteType.REMOTE
    if any(token in mode_text for token in ("onsite", "on-site", "presencial")):
        return RemoteType.ONSITE
    mode_text = re.sub(
        r"\bremote (?:debugging|procedure calls?|access|clients?|systems?)\b", "", mode_text
    )
    if any(token in mode_text for token in ("remote", "remoto", "teletrabajo", "work from home")):
        return RemoteType.REMOTE
    return fallback


def clean_job_text(value: str) -> str:
    """Preserve requirement/list boundaries for evidence classification."""
    soup = BeautifulSoup(unescape(value or ""), "html.parser")
    for element in soup.find_all(["p", "li", "br", "h2", "h3", "h4", "div"]):
        element.insert_before("\n")
        element.insert_after("\n")
    return "\n".join(
        normalize_whitespace(line) for line in soup.get_text(" ").splitlines() if line.strip()
    )


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
    parts = urlsplit(text)
    tracking = {"gh_src", "lever-source"}
    query = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if not key.lower().startswith("utm_") and key.lower() not in tracking
    ]
    return urlunsplit(
        (parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/"), urlencode(query), "")
    )


def _to_float(value: str) -> float | None:
    try:
        return float(value.replace(",", "."))
    except ValueError:
        return None


def _fold_text(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.lower())
    return "".join(character for character in decomposed if not unicodedata.combining(character))
