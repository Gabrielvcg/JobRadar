from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol

from app.models.enums import RemoteType


@dataclass(frozen=True)
class SearchConfig:
    queries: list[str]
    countries: list[str]
    cities: list[str]
    remote_from: list[str]
    languages: list[str]


@dataclass(frozen=True)
class RawJob:
    source_name: str
    source_job_id: str | None
    company_name: str
    title: str
    description: str
    requirements: str | None = None
    location: str | None = None
    country: str | None = None
    remote_type: RemoteType = RemoteType.UNKNOWN
    employment_type: str | None = None
    salary_original_text: str | None = None
    url: str | None = None
    publication_date: datetime | None = None
    expiration_date: datetime | None = None
    company_website: str | None = None
    raw_payload: dict[str, Any] = field(default_factory=dict)


class JobSourceAdapter(Protocol):
    name: str
    base_url: str | None
    enabled: bool
    min_interval_minutes: int
    minimum_score: int

    async def fetch_jobs(self, search_config: SearchConfig) -> list[RawJob]: ...


def source_settings(config: Mapping[str, Any], name: str) -> dict[str, Any]:
    sources = config.get("sources", {})
    if not isinstance(sources, dict):
        msg = "sources.yml must contain a sources mapping"
        raise ValueError(msg)
    source = sources.get(name, {})
    if not isinstance(source, dict):
        msg = f"Source {name} settings must be a mapping"
        raise ValueError(msg)
    return source
