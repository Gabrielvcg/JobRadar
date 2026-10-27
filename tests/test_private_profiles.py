from __future__ import annotations

import shutil
from pathlib import Path

import pytest
import yaml

from app.core.config import clear_config_cache
from app.core.profiles import resolve_profile_key, uses_career_radar
from app.scoring.engine import ScoringEngine


def test_career_policy_uses_private_profile_configuration(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    shutil.copytree("config", tmp_path / "config")
    config = tmp_path / "config"
    definitions = yaml.safe_load((config / "profiles.yml").read_text(encoding="utf-8"))
    definitions["profiles"]["candidate"] = definitions["profiles"].pop("engineering")
    definitions["profiles"]["office"] = definitions["profiles"].pop("operations")
    definitions["default_profile_key"] = "candidate"
    (config / "profiles.yml").write_text(yaml.safe_dump(definitions), encoding="utf-8")
    monkeypatch.setenv("CONFIG_DIR", str(config))
    clear_config_cache()
    try:
        assert resolve_profile_key(None) == "candidate"
        assert uses_career_radar("candidate") is True
        assert uses_career_radar("office") is False
        assert ScoringEngine("candidate").career_enabled is True
        assert ScoringEngine("office").career_enabled is False
    finally:
        clear_config_cache()
