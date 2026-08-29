from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = Field(default="local", alias="APP_ENV")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    app_secret_key: str = Field(default="change-me-in-production", alias="APP_SECRET_KEY")
    session_cookie_secure: bool = Field(default=False, alias="SESSION_COOKIE_SECURE")
    public_registration_enabled: bool = Field(default=True, alias="PUBLIC_REGISTRATION_ENABLED")
    database_url: str = Field(
        default="postgresql+psycopg://jobradar:jobradar@localhost:5432/jobradar",
        alias="DATABASE_URL",
    )
    config_dir: Path = Field(default=Path("config"), alias="CONFIG_DIR")
    http_timeout_seconds: float = Field(default=15.0, alias="HTTP_TIMEOUT_SECONDS")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


def resolve_config_path(file_name: str) -> Path:
    config_dir = get_settings().config_dir
    root = config_dir if config_dir.is_absolute() else Path.cwd() / config_dir
    return root / file_name


@lru_cache(maxsize=16)
def load_yaml_config(file_name: str) -> dict[str, Any]:
    path = resolve_config_path(file_name)
    with path.open("r", encoding="utf-8") as file:
        loaded = yaml.safe_load(file) or {}
    if not isinstance(loaded, dict):
        msg = f"Configuration file {path} must contain a YAML mapping"
        raise ValueError(msg)
    return loaded


def clear_config_cache() -> None:
    get_settings.cache_clear()
    load_yaml_config.cache_clear()
