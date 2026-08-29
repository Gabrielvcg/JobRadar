from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Select, and_, func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.models.enums import JobStatus, RemoteType
from app.models.job import Company, IngestionRun, JobOffer, JobSource, UserJobState
from app.scoring.engine import ScoreResult
from app.services.normalizer import NormalizedJob


@dataclass(frozen=True)
class JobFilters:
    profile_key: str | None = None
    min_score: int | None = None
    match_level: str | None = None
    technology: str | None = None
    source: str | None = None
    company: str | None = None
    salary_min: int | None = None
    salary_known: bool | None = None
    remote_type: RemoteType | None = None
    status: JobStatus | None = None
    user_id: int | None = None
    include_disabled_sources: bool = False
    published_after: datetime | None = None
    q: str | None = None
    sort: str = "score"
    order: str = "desc"
    limit: int = 50
    offset: int = 0


class JobRepository:
    def get_or_create_source(
        self,
        session: Session,
        name: str,
        enabled: bool,
        base_url: str | None,
        profile_key: str = "engineering",
    ) -> JobSource:
        source = session.scalar(select(JobSource).where(JobSource.name == name))
        if source is None:
            source = JobSource(
                name=name,
                profile_key=profile_key,
                enabled=enabled,
                base_url=base_url,
            )
            session.add(source)
            session.flush()
        else:
            source.profile_key = profile_key
            source.enabled = enabled
            source.base_url = base_url
        return source

    def get_or_create_company(
        self,
        session: Session,
        name: str,
        website: str | None,
    ) -> Company:
        normalized_name = " ".join(name.strip().split()) or "Unknown company"
        company = session.scalar(
            select(Company).where(func.lower(Company.name) == normalized_name.lower())
        )
        if company is None:
            company = Company(name=normalized_name, website=website)
            session.add(company)
            session.flush()
        elif website and not company.website:
            company.website = website
        return company

    def upsert_job(
        self,
        session: Session,
        source: JobSource,
        job: NormalizedJob,
        score: ScoreResult,
    ) -> tuple[JobOffer, bool]:
        company = self.get_or_create_company(session, job.company_name, job.company_website)
        existing = self._find_existing(session, source, job)
        now = datetime.now(UTC)
        if existing is None:
            offer = JobOffer(
                source=source,
                profile_key=source.profile_key,
                source_job_id=job.source_job_id,
                company=company,
                status=JobStatus.NEW,
                first_seen_at=now,
                last_seen_at=now,
            )
            session.add(offer)
            created = True
        else:
            offer = existing
            offer.last_seen_at = now
            created = False
        self._apply_job_fields(offer, company, job, score)
        offer.profile_key = source.profile_key
        session.flush()
        return offer, created

    def list_jobs(self, session: Session, filters: JobFilters) -> list[JobOffer]:
        statement = self._filtered_statement(filters)
        statement = self._apply_sort(statement, filters)
        statement = statement.offset(filters.offset).limit(filters.limit)
        return list(session.scalars(statement).unique())

    def get_job(self, session: Session, job_id: uuid.UUID) -> JobOffer | None:
        return session.scalar(
            select(JobOffer)
            .options(joinedload(JobOffer.company), joinedload(JobOffer.source))
            .where(JobOffer.id == job_id)
        )

    def update_status(
        self, session: Session, job_id: uuid.UUID, status: JobStatus
    ) -> JobOffer | None:
        offer = self.get_job(session, job_id)
        if offer is None:
            return None
        offer.status = status
        session.flush()
        return offer

    def update_user_status(
        self,
        session: Session,
        *,
        user_id: int,
        job_id: uuid.UUID,
        status: JobStatus,
    ) -> JobOffer | None:
        offer = self.get_job(session, job_id)
        if offer is None:
            return None
        state = session.scalar(
            select(UserJobState).where(
                UserJobState.user_id == user_id,
                UserJobState.job_offer_id == job_id,
            )
        )
        if state is None:
            state = UserJobState(user_id=user_id, job_offer_id=job_id, status=status)
            session.add(state)
        else:
            state.status = status
        session.flush()
        return offer

    def get_user_statuses(
        self, session: Session, user_id: int, jobs: list[JobOffer]
    ) -> dict[str, JobStatus]:
        job_ids = [job.id for job in jobs]
        if not job_ids:
            return {}
        rows = session.execute(
            select(UserJobState.job_offer_id, UserJobState.status).where(
                UserJobState.user_id == user_id,
                UserJobState.job_offer_id.in_(job_ids),
            )
        ).all()
        return {str(job_id): status for job_id, status in rows}

    def stats(
        self,
        session: Session,
        user_id: int | None = None,
        profile_key: str | None = None,
    ) -> dict[str, Any]:
        enabled_filter = JobSource.enabled.is_(True)
        filters: list[Any] = [enabled_filter]
        if profile_key:
            filters.append(JobOffer.profile_key == profile_key)
        total = (
            session.scalar(
                select(func.count(JobOffer.id)).join(JobOffer.source).where(*filters)
            )
            or 0
        )
        average = (
            session.scalar(
                select(func.coalesce(func.avg(JobOffer.match_score), 0))
                .join(JobOffer.source)
                .where(*filters)
            )
            or 0
        )
        by_status = {
            str(status): count
            for status, count in self._status_counts(
                session, user_id, int(total), profile_key
            ).items()
        }
        by_level = {
            str(level): count
            for level, count in session.execute(
                select(JobOffer.match_level, func.count(JobOffer.id))
                .join(JobOffer.source)
                .where(*filters)
                .group_by(JobOffer.match_level)
            ).all()
        }
        return {
            "total": int(total),
            "average_score": float(round(float(average), 2)),
            "by_status": by_status,
            "by_match_level": by_level,
        }

    def list_sources(self, session: Session, profile_key: str | None = None) -> list[JobSource]:
        statement = select(JobSource)
        if profile_key:
            statement = statement.where(JobSource.profile_key == profile_key)
        return list(session.scalars(statement.order_by(JobSource.name)))

    def list_ingestion_runs(self, session: Session, limit: int = 50) -> list[IngestionRun]:
        return list(
            session.scalars(
                select(IngestionRun).order_by(IngestionRun.started_at.desc()).limit(limit)
            )
        )

    def _find_existing(
        self, session: Session, source: JobSource, job: NormalizedJob
    ) -> JobOffer | None:
        if job.source_job_id:
            existing = session.scalar(
                select(JobOffer)
                .options(joinedload(JobOffer.company), joinedload(JobOffer.source))
                .where(JobOffer.source_id == source.id, JobOffer.source_job_id == job.source_job_id)
            )
            if existing is not None:
                return existing
        if job.url:
            existing = session.scalar(
                select(JobOffer)
                .options(joinedload(JobOffer.company), joinedload(JobOffer.source))
                .where(JobOffer.profile_key == source.profile_key, JobOffer.url == job.url)
            )
            if existing is not None:
                return existing
        return session.scalar(
            select(JobOffer)
            .options(joinedload(JobOffer.company), joinedload(JobOffer.source))
            .where(
                JobOffer.profile_key == source.profile_key,
                JobOffer.content_hash == job.content_hash,
            )
        )

    def _apply_job_fields(
        self,
        offer: JobOffer,
        company: Company,
        job: NormalizedJob,
        score: ScoreResult,
    ) -> None:
        offer.company = company
        offer.title = job.title
        offer.normalized_title = job.normalized_title
        offer.description = job.description
        offer.requirements = job.requirements
        offer.location = job.location
        offer.country = job.country
        offer.remote_type = job.remote_type
        offer.employment_type = job.employment_type
        offer.experience_min_years = job.experience_min_years
        offer.experience_max_years = job.experience_max_years
        offer.salary_min = job.salary_min
        offer.salary_max = job.salary_max
        offer.salary_currency = job.salary_currency
        offer.salary_period = job.salary_period
        offer.salary_original_text = job.salary_original_text
        offer.salary_unknown = job.salary_unknown
        offer.url = job.url
        offer.publication_date = job.publication_date
        offer.expiration_date = job.expiration_date
        offer.technologies = job.technologies
        offer.raw_payload = job.raw_payload
        offer.content_hash = job.content_hash
        offer.match_score = score.score
        offer.match_level = score.level
        offer.match_reasons = {"positive": score.positive}
        offer.negative_reasons = {"negative": score.negative}
        offer.language = job.language

    def _filtered_statement(self, filters: JobFilters) -> Select[tuple[JobOffer]]:
        statement = select(JobOffer).options(
            joinedload(JobOffer.company), joinedload(JobOffer.source)
        )
        statement = statement.join(JobOffer.company).join(JobOffer.source)
        if not filters.include_disabled_sources:
            statement = statement.where(JobSource.enabled.is_(True))
        if filters.profile_key:
            statement = statement.where(JobOffer.profile_key == filters.profile_key)
        if filters.min_score is not None:
            statement = statement.where(JobOffer.match_score >= filters.min_score)
        if filters.match_level:
            statement = statement.where(JobOffer.match_level == filters.match_level)
        if filters.technology:
            statement = statement.where(JobOffer.technologies.contains([filters.technology]))
        if filters.source:
            statement = statement.where(JobSource.name.ilike(f"%{filters.source}%"))
        if filters.company:
            statement = statement.where(Company.name.ilike(f"%{filters.company}%"))
        if filters.salary_min is not None:
            statement = statement.where(JobOffer.salary_min >= filters.salary_min)
        if filters.salary_known is True:
            statement = statement.where(
                JobOffer.salary_unknown.is_(False), JobOffer.salary_min.is_not(None)
            )
        elif filters.salary_known is False:
            statement = statement.where(
                or_(JobOffer.salary_unknown.is_(True), JobOffer.salary_min.is_(None))
            )
        if filters.remote_type is not None:
            statement = statement.where(JobOffer.remote_type == filters.remote_type)
        if filters.status is not None:
            statement = self._apply_status_filter(statement, filters)
        if filters.published_after is not None:
            statement = statement.where(JobOffer.publication_date >= filters.published_after)
        if filters.q:
            like = f"%{filters.q}%"
            statement = statement.where(
                or_(
                    JobOffer.title.ilike(like),
                    JobOffer.description.ilike(like),
                    JobOffer.requirements.ilike(like),
                    Company.name.ilike(like),
                )
            )
        return statement

    def _apply_status_filter(
        self, statement: Select[tuple[JobOffer]], filters: JobFilters
    ) -> Select[tuple[JobOffer]]:
        if filters.status is None:
            return statement
        if filters.user_id is None:
            return statement.where(JobOffer.status == filters.status)
        statement = statement.outerjoin(
            UserJobState,
            and_(
                UserJobState.job_offer_id == JobOffer.id,
                UserJobState.user_id == filters.user_id,
            ),
        )
        if filters.status == JobStatus.NEW:
            return statement.where(
                or_(UserJobState.id.is_(None), UserJobState.status == JobStatus.NEW)
            )
        return statement.where(UserJobState.status == filters.status)

    def _status_counts(
        self,
        session: Session,
        user_id: int | None,
        total: int,
        profile_key: str | None,
    ) -> dict[JobStatus, int]:
        filters: list[Any] = [JobSource.enabled.is_(True)]
        if profile_key:
            filters.append(JobOffer.profile_key == profile_key)
        if user_id is None:
            return {
                status: count
                for status, count in session.execute(
                    select(JobOffer.status, func.count(JobOffer.id))
                    .join(JobOffer.source)
                    .where(*filters)
                    .group_by(JobOffer.status)
                ).all()
            }
        rows = session.execute(
            select(UserJobState.status, func.count(UserJobState.id))
            .join(JobOffer, UserJobState.job_offer_id == JobOffer.id)
            .join(JobOffer.source)
            .where(UserJobState.user_id == user_id, *filters)
            .group_by(UserJobState.status)
        ).all()
        counts = {status: int(count) for status, count in rows}
        non_new_count = sum(count for status, count in counts.items() if status != JobStatus.NEW)
        counts[JobStatus.NEW] = max(0, total - non_new_count)
        return counts

    def _apply_sort(
        self, statement: Select[tuple[JobOffer]], filters: JobFilters
    ) -> Select[tuple[JobOffer]]:
        sort_column = JobOffer.publication_date if filters.sort == "date" else JobOffer.match_score
        if filters.order.lower() == "asc":
            return statement.order_by(sort_column.asc().nullslast(), JobOffer.created_at.desc())
        return statement.order_by(sort_column.desc().nullslast(), JobOffer.created_at.desc())
