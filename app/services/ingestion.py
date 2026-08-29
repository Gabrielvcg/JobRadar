from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.models.enums import RemoteType
from app.models.job import IngestionRun, JobOffer, JobSource
from app.repositories.jobs import JobFilters, JobRepository
from app.schemas.jobs import IngestionRunRead, IngestionSummary
from app.scoring.engine import ScoringEngine
from app.services.normalizer import JobNormalizer, NormalizedJob
from app.sources.base import JobSourceAdapter, SearchConfig
from app.sources.registry import (
    build_enabled_sources,
    configured_sources,
    load_search_config,
    source_profile_key,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SourceRunResult:
    run: IngestionRun
    fetched: int
    created: int
    updated: int
    scope_rejected: int
    score_rejected: int
    error: str | None


class IngestionService:
    def __init__(self) -> None:
        self.repository = JobRepository()
        self.normalizers: dict[str, JobNormalizer] = {}
        self.scoring_engines: dict[str, ScoringEngine] = {}

    async def run_enabled_sources(self, session: Session) -> IngestionSummary:
        self.sync_configured_sources(session)
        results: list[SourceRunResult] = []
        for adapter in build_enabled_sources():
            profile_key = source_profile_key(adapter)
            search_config = load_search_config(profile_key)
            source = self.repository.get_or_create_source(
                session,
                name=adapter.name,
                enabled=adapter.enabled,
                base_url=adapter.base_url,
                profile_key=profile_key,
            )
            session.commit()
            if _should_skip_source(source, adapter.min_interval_minutes):
                logger.info(
                    "Saltando ingesta de fuente por intervalo minimo",
                    extra={
                        "source": adapter.name,
                        "min_interval_minutes": adapter.min_interval_minutes,
                    },
                )
                continue
            logger.info("Iniciando ingesta de fuente", extra={"source": adapter.name})
            result = await self._run_source(session, adapter, search_config, source)
            results.append(result)
            if result.error:
                logger.error("La ingesta de fuente fallo", extra={"source": adapter.name})
            else:
                logger.info(
                    "Ingesta de fuente finalizada",
                    extra={
                        "source": adapter.name,
                        "fetched": result.fetched,
                        "jobs_created": result.created,
                        "jobs_updated": result.updated,
                        "jobs_scope_rejected": result.scope_rejected,
                        "jobs_score_rejected": result.score_rejected,
                    },
                )
        return IngestionSummary(
            runs=[IngestionRunRead.model_validate(result.run) for result in results],
            jobs_fetched=sum(result.fetched for result in results),
            jobs_created=sum(result.created for result in results),
            jobs_updated=sum(result.updated for result in results),
            errors=[result.error for result in results if result.error],
        )

    def sync_configured_sources(self, session: Session) -> None:
        for name, settings in configured_sources().items():
            self.repository.get_or_create_source(
                session,
                name=name,
                enabled=bool(settings.get("enabled", False)),
                base_url=_optional_str(settings.get("base_url")),
                profile_key=str(settings.get("profile_key") or "engineering"),
            )
        session.commit()

    def score_all_jobs(self, session: Session) -> int:
        count = 0
        for offer in self.repository.list_jobs(session, filters=_all_jobs_filter()):
            normalized = normalized_from_offer(offer)
            score = self._scoring_for(offer.profile_key).score(normalized)
            offer.match_score = score.score
            offer.match_level = score.level
            offer.match_reasons = {"positive": score.positive}
            offer.negative_reasons = {"negative": score.negative}
            count += 1
        session.commit()
        return count

    async def _run_source(
        self,
        session: Session,
        adapter: JobSourceAdapter,
        search_config: SearchConfig,
        source: JobSource,
    ) -> SourceRunResult:
        run = IngestionRun(source_name=adapter.name, status="running", started_at=datetime.now(UTC))
        session.add(run)
        session.commit()
        fetched = created = updated = scope_rejected = score_rejected = 0
        try:
            raw_jobs = await adapter.fetch_jobs(search_config)
            fetched = len(raw_jobs)
            normalizer = self._normalizer_for(source.profile_key)
            scoring = self._scoring_for(source.profile_key)
            for raw_job in raw_jobs:
                normalized = normalizer.normalize(raw_job)
                if not _matches_search_scope(normalized, search_config):
                    scope_rejected += 1
                    continue
                score = scoring.score(normalized)
                if score.score < adapter.minimum_score:
                    score_rejected += 1
                    continue
                _, was_created = self.repository.upsert_job(session, source, normalized, score)
                if was_created:
                    created += 1
                else:
                    updated += 1
            source.last_successful_run = datetime.now(UTC)
            source.last_error = None
            run.status = "success"
            run.jobs_fetched = fetched
            run.jobs_created = created
            run.jobs_updated = updated
            run.finished_at = datetime.now(UTC)
            session.commit()
            return SourceRunResult(
                run, fetched, created, updated, scope_rejected, score_rejected, None
            )
        except Exception as exc:
            session.rollback()
            source = self.repository.get_or_create_source(
                session,
                name=adapter.name,
                enabled=adapter.enabled,
                base_url=adapter.base_url,
                profile_key=source_profile_key(adapter),
            )
            persisted_run = session.get(IngestionRun, run.id)
            if persisted_run is None:
                persisted_run = IngestionRun(
                    id=run.id,
                    source_name=adapter.name,
                    status="failed",
                    started_at=run.started_at,
                )
                session.add(persisted_run)
            persisted_run.status = "failed"
            persisted_run.finished_at = datetime.now(UTC)
            persisted_run.jobs_fetched = fetched
            persisted_run.jobs_created = created
            persisted_run.jobs_updated = updated
            persisted_run.error = str(exc)
            source.last_error = str(exc)
            session.commit()
            return SourceRunResult(
                persisted_run,
                fetched,
                created,
                updated,
                scope_rejected,
                score_rejected,
                str(exc),
            )

    def _normalizer_for(self, profile_key: str) -> JobNormalizer:
        normalizer = self.normalizers.get(profile_key)
        if normalizer is None:
            normalizer = JobNormalizer(profile_key)
            self.normalizers[profile_key] = normalizer
        return normalizer

    def _scoring_for(self, profile_key: str) -> ScoringEngine:
        scoring = self.scoring_engines.get(profile_key)
        if scoring is None:
            scoring = ScoringEngine(profile_key)
            self.scoring_engines[profile_key] = scoring
        return scoring


def normalized_from_offer(offer: JobOffer) -> NormalizedJob:
    return NormalizedJob(
        source_job_id=offer.source_job_id,
        company_name=offer.company.name,
        company_website=offer.company.website,
        title=offer.title,
        normalized_title=offer.normalized_title,
        description=offer.description,
        requirements=offer.requirements,
        location=offer.location,
        country=offer.country,
        remote_type=offer.remote_type,
        employment_type=offer.employment_type,
        experience_min_years=offer.experience_min_years,
        experience_max_years=offer.experience_max_years,
        salary_min=offer.salary_min,
        salary_max=offer.salary_max,
        salary_currency=offer.salary_currency,
        salary_period=offer.salary_period,
        salary_original_text=offer.salary_original_text,
        salary_unknown=offer.salary_unknown,
        url=offer.url,
        publication_date=offer.publication_date,
        expiration_date=offer.expiration_date,
        technologies=offer.technologies,
        raw_payload=offer.raw_payload,
        content_hash=offer.content_hash,
        language=offer.language,
    )


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _all_jobs_filter() -> JobFilters:
    return JobFilters(limit=10_000, offset=0, include_disabled_sources=True)


def _should_skip_source(source: JobSource, min_interval_minutes: int) -> bool:
    if min_interval_minutes <= 0 or source.last_successful_run is None:
        return False
    last_successful_run = source.last_successful_run
    if last_successful_run.tzinfo is None:
        last_successful_run = last_successful_run.replace(tzinfo=UTC)
    return datetime.now(UTC) - last_successful_run < timedelta(minutes=min_interval_minutes)


def _matches_search_scope(job: NormalizedJob, search_config: SearchConfig) -> bool:
    allowed_languages = {language.lower() for language in search_config.languages}
    if allowed_languages and job.language and job.language.lower() not in allowed_languages:
        return False
    return _matches_target_location(job, search_config)


def _matches_target_location(job: NormalizedJob, search_config: SearchConfig) -> bool:
    location = f"{job.location or ''} {job.country or ''}".lower()
    target_terms = _target_location_terms(search_config)
    if job.remote_type == RemoteType.REMOTE:
        if not location:
            return True
        remote_terms = target_terms | _remote_region_terms(search_config) | {
            "remote",
            "worldwide",
            "world",
            "anywhere",
            "global",
            "europe",
            "emea",
        }
        return any(term in location for term in remote_terms)
    return any(term in location for term in target_terms)


def _target_location_terms(search_config: SearchConfig) -> set[str]:
    terms = {
        term.lower()
        for term in [*search_config.countries, *search_config.cities, *search_config.remote_from]
        if term
    }
    if "spain" in terms:
        terms.add("espana")
        terms.add("espa\u00f1a")
    if "european union" in terms:
        terms.add("europe")
    return terms


def _remote_region_terms(search_config: SearchConfig) -> set[str]:
    countries = {country.lower() for country in search_config.countries}
    if "european union" not in countries:
        return set()
    return {
        "austria",
        "belgium",
        "bulgaria",
        "croatia",
        "cyprus",
        "czechia",
        "czech republic",
        "denmark",
        "estonia",
        "finland",
        "france",
        "germany",
        "greece",
        "hungary",
        "ireland",
        "italy",
        "latvia",
        "lithuania",
        "luxembourg",
        "malta",
        "netherlands",
        "poland",
        "portugal",
        "romania",
        "slovakia",
        "slovenia",
        "sweden",
    }
