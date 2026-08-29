"""add users and per-user job states

Revision ID: 0002_add_user_accounts
Revises: 0001_create_core_tables
Create Date: 2026-06-27 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_add_user_accounts"
down_revision: str | None = "0001_create_core_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("display_name", sa.String(length=120), nullable=False),
        sa.Column("password_hash", sa.String(length=300), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index("ix_users_email", "users", ["email"])

    op.create_table(
        "user_job_states",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "job_offer_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("job_offers.id"),
            nullable=False,
        ),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="new"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("user_id", "job_offer_id", name="uq_user_job_states_user_job"),
    )
    op.create_index("ix_user_job_states_user_status", "user_job_states", ["user_id", "status"])
    op.create_index("ix_user_job_states_job_offer_id", "user_job_states", ["job_offer_id"])


def downgrade() -> None:
    op.drop_index("ix_user_job_states_job_offer_id", table_name="user_job_states")
    op.drop_index("ix_user_job_states_user_status", table_name="user_job_states")
    op.drop_table("user_job_states")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
