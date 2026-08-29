from __future__ import annotations

from app.core.config import load_yaml_config
from app.scoring.text import detect_technologies


def test_detects_technologies_from_config() -> None:
    config = load_yaml_config("scoring.yml")

    technologies = detect_technologies(
        "Java Spring Boot REST APIs on PostgreSQL, Docker, AWS, Terraform and GitHub Actions",
        config,
    )

    assert "Java" in technologies
    assert "Spring Boot" in technologies
    assert "PostgreSQL" in technologies
    assert "AWS" in technologies
    assert "Terraform" in technologies
    assert "GitHub Actions" in technologies


def test_detects_operations_profile_administrative_skills() -> None:
    config = load_yaml_config("profiles/operations/scoring.yml")

    technologies = detect_technologies(
        "Manejo de Excel, Word, Outlook, Power BI, Microdata y gestion documental",
        config,
    )

    assert "Excel" in technologies
    assert "Word" in technologies
    assert "Outlook" in technologies
    assert "Power BI" in technologies
    assert "Microdata" in technologies
    assert "Gestion documental" in technologies


def test_public_configuration_has_valid_utf8_text() -> None:
    sources = load_yaml_config("sources.yml")
    scoring = load_yaml_config("profiles/operations/scoring.yml")
    serialized = f"{sources!r}{scoring!r}"

    assert "Ã" not in serialized
    assert "Â" not in serialized
    assert "portugués" in serialized
    assert "almería" in serialized
