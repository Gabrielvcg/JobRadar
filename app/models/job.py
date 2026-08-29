from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import JobStatus, RemoteType


def enum_values(enum_class: type[RemoteType] | type[JobStatus]) -> list[str]:
    return [member.value for member in enum_class]


class JobSource(TimestampMixin, Base):
    __tablename__ = "job_sources"
    __table_args__ = (
        UniqueConstraint("name", name="uq_job_sources_name"),
        Index("ix_job_sources_profile_key", "profile_key"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    profile_key: Mapped[str] = mapped_column(String(80), default="engineering", nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    base_url: Mapped[str | None] = mapped_column(String(500))
    last_successful_run: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)

    offers: Mapped[list[JobOffer]] = relationship(back_populates="source")


class Company(TimestampMixin, Base):
    __tablename__ = "companies"
    __table_args__ = (UniqueConstraint("name", name="uq_companies_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(240), nullable=False)
    website: Mapped[str | None] = mapped_column(String(500))

    offers: Mapped[list[JobOffer]] = relationship(back_populates="company")


class User(TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("email", name="uq_users_email"),
        Index("ix_users_email", "email"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(300), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    job_states: Mapped[list[UserJobState]] = relationship(back_populates="user")


class JobOffer(TimestampMixin, Base):
    __tablename__ = "job_offers"
    __table_args__ = (
        UniqueConstraint("source_id", "source_job_id", name="uq_job_offers_source_job_id"),
        Index("ix_job_offers_match_score", "match_score"),
        Index("ix_job_offers_publication_date", "publication_date"),
        Index("ix_job_offers_status", "status"),
        Index("ix_job_offers_remote_type", "remote_type"),
        Index("ix_job_offers_salary", "salary_min", "salary_max"),
        Index("ix_job_offers_profile_key", "profile_key"),
        Index("ix_job_offers_source_id", "source_id"),
        Index("ix_job_offers_url", "url"),
        Index("ix_job_offers_content_hash", "content_hash"),
        Index("ix_job_offers_technologies_gin", "technologies", postgresql_using="gin"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_id: Mapped[int] = mapped_column(ForeignKey("job_sources.id"), nullable=False)
    profile_key: Mapped[str] = mapped_column(String(80), default="engineering", nullable=False)
    source_job_id: Mapped[str | None] = mapped_column(String(240))
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    normalized_title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    requirements: Mapped[str | None] = mapped_column(Text)
    location: Mapped[str | None] = mapped_column(String(500))
    country: Mapped[str | None] = mapped_column(String(120))
    remote_type: Mapped[RemoteType] = mapped_column(
        Enum(RemoteType, values_callable=enum_values, native_enum=False),
        default=RemoteType.UNKNOWN,
        nullable=False,
    )
    employment_type: Mapped[str | None] = mapped_column(String(120))
    experience_min_years: Mapped[float | None] = mapped_column(Float)
    experience_max_years: Mapped[float | None] = mapped_column(Float)
    salary_min: Mapped[int | None] = mapped_column(Integer)
    salary_max: Mapped[int | None] = mapped_column(Integer)
    salary_currency: Mapped[str | None] = mapped_column(String(12))
    salary_period: Mapped[str | None] = mapped_column(String(40))
    salary_original_text: Mapped[str | None] = mapped_column(String(300))
    salary_unknown: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    url: Mapped[str | None] = mapped_column(String(1000))
    publication_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expiration_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    technologies: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    raw_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    match_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    match_level: Mapped[str] = mapped_column(String(20), default="low", nullable=False)
    match_reasons: Mapped[dict[str, list[str]]] = mapped_column(JSONB, default=dict, nullable=False)
    negative_reasons: Mapped[dict[str, list[str]]] = mapped_column(
        JSONB, default=dict, nullable=False
    )
    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus, values_callable=enum_values, native_enum=False),
        default=JobStatus.NEW,
        nullable=False,
    )
    language: Mapped[str | None] = mapped_column(String(10))
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    source: Mapped[JobSource] = relationship(back_populates="offers")
    company: Mapped[Company] = relationship(back_populates="offers")
    user_states: Mapped[list[UserJobState]] = relationship(back_populates="job_offer")


class UserJobState(TimestampMixin, Base):
    __tablename__ = "user_job_states"
    __table_args__ = (
        UniqueConstraint("user_id", "job_offer_id", name="uq_user_job_states_user_job"),
        Index("ix_user_job_states_user_status", "user_id", "status"),
        Index("ix_user_job_states_job_offer_id", "job_offer_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    job_offer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("job_offers.id"), nullable=False
    )
    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus, values_callable=enum_values, native_enum=False),
        default=JobStatus.NEW,
        nullable=False,
    )

    user: Mapped[User] = relationship(back_populates="job_states")
    job_offer: Mapped[JobOffer] = relationship(back_populates="user_states")


class IngestionRun(TimestampMixin, Base):
    __tablename__ = "ingestion_runs"
    __table_args__ = (
        Index("ix_ingestion_runs_started_at", "started_at"),
        Index("ix_ingestion_runs_source_name", "source_name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_name: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    jobs_fetched: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    jobs_created: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    jobs_updated: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error: Mapped[str | None] = mapped_column(Text)
