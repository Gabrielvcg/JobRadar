from __future__ import annotations

from dataclasses import dataclass

from app.core.config import load_yaml_config

FALLBACK_PROFILE_KEY = "engineering"


@dataclass(frozen=True)
class ProfileDefinition:
    key: str
    label: str
    description: str
    profile_config: str
    scoring_config: str
    searches_config: str


def load_profiles() -> dict[str, ProfileDefinition]:
    config = load_yaml_config("profiles.yml")
    raw_profiles = config.get("profiles", {})
    if not isinstance(raw_profiles, dict) or not raw_profiles:
        return {
            FALLBACK_PROFILE_KEY: ProfileDefinition(
                key=FALLBACK_PROFILE_KEY,
                label="Engineering",
                description="Backend Java / AppSec",
                profile_config="profile.yml",
                scoring_config="scoring.yml",
                searches_config="searches.yml",
            )
        }
    profiles: dict[str, ProfileDefinition] = {}
    for key, raw_profile in raw_profiles.items():
        if not isinstance(raw_profile, dict):
            continue
        profile_key = str(key)
        profiles[profile_key] = ProfileDefinition(
            key=profile_key,
            label=str(raw_profile.get("label") or profile_key.title()),
            description=str(raw_profile.get("description") or ""),
            profile_config=str(raw_profile.get("profile_config") or "profile.yml"),
            scoring_config=str(raw_profile.get("scoring_config") or "scoring.yml"),
            searches_config=str(raw_profile.get("searches_config") or "searches.yml"),
        )
    if not profiles:
        msg = "profiles.yml must contain at least one profile"
        raise ValueError(msg)
    return profiles


def default_profile_key() -> str:
    config = load_yaml_config("profiles.yml")
    key = str(config.get("default_profile_key") or FALLBACK_PROFILE_KEY)
    return key if key in load_profiles() else FALLBACK_PROFILE_KEY


def resolve_profile_key(profile_key: str | None) -> str:
    profiles = load_profiles()
    if profile_key and profile_key in profiles:
        return profile_key
    default_key = default_profile_key()
    return default_key if default_key in profiles else next(iter(profiles))


def get_profile(profile_key: str | None = None) -> ProfileDefinition:
    key = resolve_profile_key(profile_key)
    return load_profiles()[key]
