"""create core tables

Revision ID: 0001_create_core_tables
Revises:
Create Date: 2026-06-27 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_create_core_tables"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "job_sources",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("base_url", sa.String(length=500), nullable=True),
        sa.Column("last_successful_run", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("name", name="uq_job_sources_name"),
    )

    op.create_table(
        "companies",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=240), nullable=False),
        sa.Column("website", sa.String(length=500), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("name", name="uq_companies_name"),
    )

    op.create_table(
        "ingestion_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("source_name", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("jobs_fetched", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("jobs_created", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("jobs_updated", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_ingestion_runs_started_at", "ingestion_runs", ["started_at"])
    op.create_index("ix_ingestion_runs_source_name", "ingestion_runs", ["source_name"])

    op.create_table(
        "job_offers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("source_id", sa.Integer(), sa.ForeignKey("job_sources.id"), nullable=False),
        sa.Column("source_job_id", sa.String(length=240), nullable=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("normalized_title", sa.String(length=500), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("requirements", sa.Text(), nullable=True),
        sa.Column("location", sa.String(length=500), nullable=True),
        sa.Column("country", sa.String(length=120), nullable=True),
        sa.Column("remote_type", sa.String(length=20), nullable=False, server_default="unknown"),
        sa.Column("employment_type", sa.String(length=120), nullable=True),
        sa.Column("experience_min_years", sa.Float(), nullable=True),
        sa.Column("experience_max_years", sa.Float(), nullable=True),
        sa.Column("salary_min", sa.Integer(), nullable=True),
        sa.Column("salary_max", sa.Integer(), nullable=True),
        sa.Column("salary_currency", sa.String(length=12), nullable=True),
        sa.Column("salary_period", sa.String(length=40), nullable=True),
        sa.Column("salary_original_text", sa.String(length=300), nullable=True),
        sa.Column("salary_unknown", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("url", sa.String(length=1000), nullable=True),
        sa.Column("publication_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expiration_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "technologies",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
        sa.Column(
            "raw_payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("match_score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("match_level", sa.String(length=20), nullable=False, server_default="low"),
        sa.Column(
            "match_reasons",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "negative_reasons",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="new"),
        sa.Column("language", sa.String(length=10), nullable=True),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("source_id", "source_job_id", name="uq_job_offers_source_job_id"),
    )
    op.create_index("ix_job_offers_match_score", "job_offers", ["match_score"])
    op.create_index("ix_job_offers_publication_date", "job_offers", ["publication_date"])
    op.create_index("ix_job_offers_status", "job_offers", ["status"])
    op.create_index("ix_job_offers_remote_type", "job_offers", ["remote_type"])
    op.create_index("ix_job_offers_salary", "job_offers", ["salary_min", "salary_max"])
    op.create_index("ix_job_offers_source_id", "job_offers", ["source_id"])
    op.create_index("ix_job_offers_url", "job_offers", ["url"])
    op.create_index("ix_job_offers_content_hash", "job_offers", ["content_hash"])
    op.create_index(
        "ix_job_offers_technologies_gin",
        "job_offers",
        ["technologies"],
        postgresql_using="gin",
    )


def downgrade() -> None:
    op.drop_index("ix_job_offers_technologies_gin", table_name="job_offers")
    op.drop_index("ix_job_offers_content_hash", table_name="job_offers")
    op.drop_index("ix_job_offers_url", table_name="job_offers")
    op.drop_index("ix_job_offers_source_id", table_name="job_offers")
    op.drop_index("ix_job_offers_salary", table_name="job_offers")
    op.drop_index("ix_job_offers_remote_type", table_name="job_offers")
    op.drop_index("ix_job_offers_status", table_name="job_offers")
    op.drop_index("ix_job_offers_publication_date", table_name="job_offers")
    op.drop_index("ix_job_offers_match_score", table_name="job_offers")
    op.drop_table("job_offers")
    op.drop_index("ix_ingestion_runs_source_name", table_name="ingestion_runs")
    op.drop_index("ix_ingestion_runs_started_at", table_name="ingestion_runs")
    op.drop_table("ingestion_runs")
    op.drop_table("companies")
    op.drop_table("job_sources")
