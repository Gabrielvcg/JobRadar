from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import JobStatus, RemoteType


class JobOfferRead(BaseModel):
    id: uuid.UUID
    profile_key: str
    source_name: str
    source_job_id: str | None
    company_name: str
    title: str
    normalized_title: str
    description: str
    requirements: str | None
    location: str | None
    country: str | None
    remote_type: RemoteType
    employment_type: str | None
    experience_min_years: float | None
    experience_max_years: float | None
    salary_min: int | None
    salary_max: int | None
    salary_currency: str | None
    salary_period: str | None
    salary_original_text: str | None
    salary_unknown: bool
    url: str | None
    publication_date: datetime | None
    expiration_date: datetime | None
    technologies: list[str]
    content_hash: str
    match_score: int
    match_level: str
    match_reasons: dict[str, list[str]]
    negative_reasons: dict[str, list[str]]
    status: JobStatus
    language: str | None
    first_seen_at: datetime
    last_seen_at: datetime
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class JobStatusUpdate(BaseModel):
    status: JobStatus


class UserRead(BaseModel):
    id: int
    email: str
    display_name: str
    is_admin: bool

    model_config = ConfigDict(from_attributes=True)


class JobStats(BaseModel):
    total: int
    average_score: float
    by_status: dict[str, int]
    by_match_level: dict[str, int]


class JobsResponse(BaseModel):
    items: list[JobOfferRead]
    limit: int = Field(ge=1, le=200)
    offset: int = Field(ge=0)


class IngestionRunRead(BaseModel):
    id: uuid.UUID
    source_name: str
    status: str
    started_at: datetime
    finished_at: datetime | None
    jobs_fetched: int
    jobs_created: int
    jobs_updated: int
    error: str | None

    model_config = ConfigDict(from_attributes=True)


class SourceRead(BaseModel):
    id: int
    name: str
    profile_key: str
    enabled: bool
    base_url: str | None
    last_successful_run: datetime | None
    last_error: str | None

    model_config = ConfigDict(from_attributes=True)


class IngestionSummary(BaseModel):
    runs: list[IngestionRunRead]
    jobs_fetched: int
    jobs_created: int
    jobs_updated: int
    errors: list[str]


def job_offer_to_read(job: Any, status_override: JobStatus | None = None) -> JobOfferRead:
    return JobOfferRead(
        id=job.id,
        profile_key=job.profile_key,
        source_name=job.source.name,
        source_job_id=job.source_job_id,
        company_name=job.company.name,
        title=job.title,
        normalized_title=job.normalized_title,
        description=job.description,
        requirements=job.requirements,
        location=job.location,
        country=job.country,
        remote_type=job.remote_type,
        employment_type=job.employment_type,
        experience_min_years=job.experience_min_years,
        experience_max_years=job.experience_max_years,
        salary_min=job.salary_min,
        salary_max=job.salary_max,
        salary_currency=job.salary_currency,
        salary_period=job.salary_period,
        salary_original_text=job.salary_original_text,
        salary_unknown=job.salary_unknown,
        url=job.url,
        publication_date=job.publication_date,
        expiration_date=job.expiration_date,
        technologies=job.technologies,
        content_hash=job.content_hash,
        match_score=job.match_score,
        match_level=job.match_level,
        match_reasons=job.match_reasons,
        negative_reasons=job.negative_reasons,
        status=status_override or job.status,
        language=job.language,
        first_seen_at=job.first_seen_at,
        last_seen_at=job.last_seen_at,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )
