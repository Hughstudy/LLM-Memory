from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


compaction_status_enum = sa.Enum(
    "active",
    "batched",
    "compacted",
    "superseded",
    name="compactionstatus",
)
summary_kind_enum = sa.Enum(
    "leaf",
    "condensed",
    "root_candidate",
    name="summarykind",
)
job_status_enum = sa.Enum(
    "queued",
    "running",
    "succeeded",
    "failed",
    name="jobstatus",
)
compaction_source_type_enum = sa.Enum(
    "raw",
    "summary",
    name="compactionsourcetype",
)


def upgrade() -> None:
    bind = op.get_bind()
    compaction_status_enum.create(bind, checkfirst=True)
    summary_kind_enum.create(bind, checkfirst=True)
    job_status_enum.create(bind, checkfirst=True)
    compaction_source_type_enum.create(bind, checkfirst=True)

    op.create_table(
        "memory_categories",
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_index("ix_categories_name", "memory_categories", ["name"], unique=True)

    op.create_table(
        "delegation_grants",
        sa.Column("conversation_scope", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("token_cap", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_grants_expires", "delegation_grants", ["expires_at"], unique=False)
    op.create_index("ix_grants_revoked", "delegation_grants", ["revoked_at"], unique=False)

    op.create_table(
        "raw_memories",
        sa.Column("category_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("fact", sa.Text(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=False),
        sa.Column("behavior", sa.Text(), nullable=False),
        sa.Column("content_text", sa.Text(), nullable=False),
        sa.Column("token_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("compaction_status", compaction_status_enum, nullable=False),
        sa.Column("compaction_batch_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(["category_id"], ["memory_categories.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_raw_memories_category_created",
        "raw_memories",
        ["category_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_raw_memories_category_status",
        "raw_memories",
        ["category_id", "compaction_status"],
        unique=False,
    )
    op.create_index("ix_raw_memories_status", "raw_memories", ["compaction_status"], unique=False)

    op.create_table(
        "memory_summaries",
        sa.Column("category_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("level", sa.Integer(), server_default="0", nullable=False),
        sa.Column("kind", summary_kind_enum, nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("summary_text", sa.Text(), nullable=False),
        sa.Column("fact_summary", sa.Text(), nullable=False),
        sa.Column("comment_summary", sa.Text(), nullable=False),
        sa.Column("behavior_summary", sa.Text(), nullable=False),
        sa.Column("token_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("source_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("descendant_raw_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("compaction_status", compaction_status_enum, nullable=False),
        sa.Column("compaction_batch_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(["category_id"], ["memory_categories.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_summaries_category_level",
        "memory_summaries",
        ["category_id", "level"],
        unique=False,
    )
    op.create_index(
        "ix_summaries_category_status",
        "memory_summaries",
        ["category_id", "compaction_status"],
        unique=False,
    )
    op.create_index("ix_summaries_level", "memory_summaries", ["level"], unique=False)
    op.create_index("ix_summaries_status", "memory_summaries", ["compaction_status"], unique=False)

    op.create_table(
        "compaction_jobs",
        sa.Column("category_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_type", compaction_source_type_enum, nullable=False),
        sa.Column("status", job_status_enum, nullable=False),
        sa.Column("input_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("output_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("llm_model", sa.String(length=128), nullable=False),
        sa.Column("prompt_version", sa.String(length=64), nullable=False),
        sa.Column("error_text", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["category_id"], ["memory_categories.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_jobs_category_status",
        "compaction_jobs",
        ["category_id", "status"],
        unique=False,
    )
    op.create_index("ix_jobs_status", "compaction_jobs", ["status"], unique=False)

    op.create_table(
        "summary_parent_links",
        sa.Column("summary_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("parent_summary_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("position", sa.Integer(), server_default="0", nullable=False),
        sa.ForeignKeyConstraint(["parent_summary_id"], ["memory_summaries.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["summary_id"], ["memory_summaries.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("summary_id", "parent_summary_id"),
    )
    op.create_index(
        "ix_sp_links_parent",
        "summary_parent_links",
        ["parent_summary_id"],
        unique=False,
    )
    op.create_index(
        "ix_sp_links_summary",
        "summary_parent_links",
        ["summary_id"],
        unique=False,
    )

    op.create_table(
        "summary_raw_memory_links",
        sa.Column("summary_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("raw_memory_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("position", sa.Integer(), server_default="0", nullable=False),
        sa.ForeignKeyConstraint(["raw_memory_id"], ["raw_memories.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["summary_id"], ["memory_summaries.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("summary_id", "raw_memory_id"),
    )
    op.create_index(
        "ix_srm_links_raw",
        "summary_raw_memory_links",
        ["raw_memory_id"],
        unique=False,
    )
    op.create_index(
        "ix_srm_links_summary",
        "summary_raw_memory_links",
        ["summary_id"],
        unique=False,
    )

    op.execute(
        "CREATE INDEX ix_raw_memories_content_text_fts ON raw_memories "
        "USING GIN (to_tsvector('english', content_text))"
    )
    op.execute(
        "CREATE INDEX ix_memory_summaries_summary_text_fts ON memory_summaries "
        "USING GIN (to_tsvector('english', summary_text))"
    )


def downgrade() -> None:
    op.drop_index("ix_memory_summaries_summary_text_fts", table_name="memory_summaries")
    op.drop_index("ix_raw_memories_content_text_fts", table_name="raw_memories")

    op.drop_index("ix_srm_links_summary", table_name="summary_raw_memory_links")
    op.drop_index("ix_srm_links_raw", table_name="summary_raw_memory_links")
    op.drop_table("summary_raw_memory_links")

    op.drop_index("ix_sp_links_summary", table_name="summary_parent_links")
    op.drop_index("ix_sp_links_parent", table_name="summary_parent_links")
    op.drop_table("summary_parent_links")

    op.drop_index("ix_jobs_status", table_name="compaction_jobs")
    op.drop_index("ix_jobs_category_status", table_name="compaction_jobs")
    op.drop_table("compaction_jobs")

    op.drop_index("ix_summaries_status", table_name="memory_summaries")
    op.drop_index("ix_summaries_level", table_name="memory_summaries")
    op.drop_index("ix_summaries_category_status", table_name="memory_summaries")
    op.drop_index("ix_summaries_category_level", table_name="memory_summaries")
    op.drop_table("memory_summaries")

    op.drop_index("ix_raw_memories_status", table_name="raw_memories")
    op.drop_index("ix_raw_memories_category_status", table_name="raw_memories")
    op.drop_index("ix_raw_memories_category_created", table_name="raw_memories")
    op.drop_table("raw_memories")

    op.drop_index("ix_grants_revoked", table_name="delegation_grants")
    op.drop_index("ix_grants_expires", table_name="delegation_grants")
    op.drop_table("delegation_grants")

    op.drop_index("ix_categories_name", table_name="memory_categories")
    op.drop_table("memory_categories")

    bind = op.get_bind()
    compaction_source_type_enum.drop(bind, checkfirst=True)
    job_status_enum.drop(bind, checkfirst=True)
    summary_kind_enum.drop(bind, checkfirst=True)
    compaction_status_enum.drop(bind, checkfirst=True)
