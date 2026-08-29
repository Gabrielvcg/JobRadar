from __future__ import annotations

from app.models.enums import RemoteType
from app.scoring.text import (
    clean_html,
    content_hash,
    detect_language,
    detect_remote_type,
    extract_experience_years,
)


def test_clean_html_removes_tags() -> None:
    assert clean_html("<p>Java <strong>Backend</strong></p>") == "Java Backend"


def test_extracts_experience_range() -> None:
    assert extract_experience_years("1-3 years of backend experience") == (1.0, 3.0)


def test_extracts_experience_range_with_typographic_dash() -> None:
    assert extract_experience_years("3–5 years of Java experience") == (3.0, 5.0)


def test_extracts_spanish_experience_years() -> None:
    assert extract_experience_years("Al menos 2 años de experiencia") == (2.0, 2.0)


def test_detects_remote_type() -> None:
    assert detect_remote_type("Remote from Spain") == RemoteType.REMOTE
    assert detect_remote_type("Sevilla hybrid") == RemoteType.HYBRID


def test_detects_basic_language() -> None:
    assert detect_language("Java developer with salary and remote work") == "en"
    assert detect_language("Desarrollador con experiencia y salario competitivo") == "es"
    assert detect_language("Pessoa com experi\u00eancia, sal\u00e1rio e trabalho remoto") == "pt"
    assert (
        detect_language(
            "Estagi\u00e1rio Contabilidade. Conhecimentos de ferramentas informaticas."
        )
        == "pt"
    )
    assert detect_language("Wir suchen Entwickler mit Erfahrung und Bewerbung auf Deutsch") == "de"


def test_content_hash_is_stable() -> None:
    first = content_hash("Company", "Backend Java", "Sevilla", "Build APIs")
    second = content_hash(" company ", "backend java", "sevilla", "Build   APIs")

    assert first == second
