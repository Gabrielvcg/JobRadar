"""add job profile keys

Revision ID: 0003_add_job_profiles
Revises: 0002_add_user_accounts
Create Date: 2026-07-02 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_add_job_profiles"
down_revision: str | None = "0002_add_user_accounts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "job_sources",
        sa.Column(
            "profile_key",
            sa.String(length=80),
            nullable=False,
            server_default="engineering",
        ),
    )
    op.add_column(
        "job_offers",
        sa.Column(
            "profile_key",
            sa.String(length=80),
            nullable=False,
            server_default="engineering",
        ),
    )
    op.create_index("ix_job_sources_profile_key", "job_sources", ["profile_key"])
    op.create_index("ix_job_offers_profile_key", "job_offers", ["profile_key"])


def downgrade() -> None:
    op.drop_index("ix_job_offers_profile_key", table_name="job_offers")
    op.drop_index("ix_job_sources_profile_key", table_name="job_sources")
    op.drop_column("job_offers", "profile_key")
    op.drop_column("job_sources", "profile_key")
