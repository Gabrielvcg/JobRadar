from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.core.config import load_yaml_config
from app.core.profiles import get_profile, resolve_profile_key
from app.models.enums import RemoteType
from app.scoring.salary import extract_salary
from app.scoring.text import (
    canonical_url,
    clean_html,
    content_hash,
    detect_language,
    detect_remote_type,
    detect_technologies,
    extract_experience_years,
    normalize_title,
)
from app.sources.base import RawJob


@dataclass(frozen=True)
class NormalizedJob:
    source_job_id: str | None
    company_name: str
    company_website: str | None
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
    raw_payload: dict[str, Any]
    content_hash: str
    language: str | None


class JobNormalizer:
    def __init__(self, profile_key: str | None = None) -> None:
        self.profile_key = resolve_profile_key(profile_key)
        self.scoring_config = load_yaml_config(get_profile(self.profile_key).scoring_config)

    def normalize(self, raw_job: RawJob) -> NormalizedJob:
        description = clean_html(raw_job.description)
        requirements = clean_html(raw_job.requirements or "") or None
        combined_text = " ".join(
            part
            for part in (
                raw_job.title,
                description,
                requirements or "",
                raw_job.location or "",
                raw_job.salary_original_text or "",
            )
            if part
        )
        salary_text = " ".join(
            part for part in (combined_text, raw_job.salary_original_text or "") if part
        )
        salary = extract_salary(salary_text)
        exp_min, exp_max = extract_experience_years(combined_text)
        remote_type = detect_remote_type(combined_text, raw_job.remote_type)
        normalized = normalize_title(raw_job.title)
        url = canonical_url(raw_job.url)
        job_hash = content_hash(raw_job.company_name, normalized, raw_job.location, description)
        technologies = detect_technologies(combined_text, self.scoring_config)
        language = detect_language(combined_text)
        return NormalizedJob(
            source_job_id=raw_job.source_job_id,
            company_name=raw_job.company_name.strip() or "Unknown company",
            company_website=canonical_url(raw_job.company_website),
            title=clean_html(raw_job.title) or "Untitled job",
            normalized_title=normalized,
            description=description,
            requirements=requirements,
            location=raw_job.location,
            country=raw_job.country,
            remote_type=remote_type,
            employment_type=raw_job.employment_type,
            experience_min_years=exp_min,
            experience_max_years=exp_max,
            salary_min=salary.salary_min,
            salary_max=salary.salary_max,
            salary_currency=salary.currency,
            salary_period=salary.period,
            salary_original_text=salary.original_text or raw_job.salary_original_text,
            salary_unknown=salary.unknown,
            url=url,
            publication_date=raw_job.publication_date,
            expiration_date=raw_job.expiration_date,
            technologies=technologies,
            raw_payload=raw_job.raw_payload,
            content_hash=job_hash,
            language=language,
        )
