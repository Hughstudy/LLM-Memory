from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0002_integrity_and_retrieval_hardening"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "memory_summaries",
        "descendant_raw_count",
        existing_type=sa.Integer(),
        type_=sa.BigInteger(),
        existing_nullable=False,
        existing_server_default="0",
    )
    op.create_index(
        "ix_jobs_status_created",
        "compaction_jobs",
        ["status", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_grants_revoked_expires",
        "delegation_grants",
        ["revoked_at", "expires_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_grants_revoked_expires", table_name="delegation_grants")
    op.drop_index("ix_jobs_status_created", table_name="compaction_jobs")
    op.alter_column(
        "memory_summaries",
        "descendant_raw_count",
        existing_type=sa.BigInteger(),
        type_=sa.Integer(),
        existing_nullable=False,
        existing_server_default="0",
    )
