from __future__ import annotations

import datetime
import uuid
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from lcmemory.db.base import Base, IdMixin, TimestampMixin
from lcmemory.domain.enums import (
    CompactionSourceType,
    CompactionStatus,
    JobStatus,
    SummaryKind,
)


class MemoryCategory(Base, IdMixin, TimestampMixin):
    __tablename__ = "memory_categories"

    name: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    raw_memories: Mapped[list[RawMemory]] = relationship(
        back_populates="category", lazy="selectin", cascade="all, delete-orphan"
    )
    summaries: Mapped[list[MemorySummary]] = relationship(
        back_populates="category", lazy="selectin", cascade="all, delete-orphan"
    )
    compaction_jobs: Mapped[list[CompactionJob]] = relationship(
        back_populates="category", lazy="noload"
    )

    __table_args__ = (Index("ix_categories_name", "name", unique=True),)


class RawMemory(Base, IdMixin, TimestampMixin):
    __tablename__ = "raw_memories"

    category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("memory_categories.id", ondelete="CASCADE"), nullable=False
    )
    fact: Mapped[str] = mapped_column(Text, nullable=False)
    comment: Mapped[str] = mapped_column(Text, nullable=False)
    behavior: Mapped[str] = mapped_column(Text, nullable=False)
    content_text: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    compaction_status: Mapped[CompactionStatus] = mapped_column(
        default=CompactionStatus.ACTIVE, nullable=False
    )
    compaction_batch_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    category: Mapped[MemoryCategory] = relationship(back_populates="raw_memories")
    summary_links: Mapped[list[SummaryRawMemoryLink]] = relationship(
        back_populates="raw_memory", lazy="noload"
    )

    __table_args__ = (
        Index("ix_raw_memories_category_status", "category_id", "compaction_status"),
        Index("ix_raw_memories_category_created", "category_id", "created_at"),
        Index("ix_raw_memories_status", "compaction_status"),
    )


class MemorySummary(Base, IdMixin, TimestampMixin):
    __tablename__ = "memory_summaries"

    category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("memory_categories.id", ondelete="CASCADE"), nullable=False
    )
    level: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    kind: Mapped[SummaryKind] = mapped_column(default=SummaryKind.LEAF, nullable=False)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    fact_summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    comment_summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    behavior_summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    token_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    source_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    descendant_raw_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    compaction_status: Mapped[CompactionStatus] = mapped_column(
        default=CompactionStatus.ACTIVE, nullable=False
    )
    compaction_batch_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    category: Mapped[MemoryCategory] = relationship(back_populates="summaries")
    raw_memory_links: Mapped[list[SummaryRawMemoryLink]] = relationship(
        back_populates="summary", lazy="selectin", cascade="all, delete-orphan"
    )
    parent_links: Mapped[list[SummaryParentLink]] = relationship(
        back_populates="summary",
        lazy="selectin",
        cascade="all, delete-orphan",
        foreign_keys="[SummaryParentLink.summary_id]",
    )
    child_links: Mapped[list[SummaryParentLink]] = relationship(
        back_populates="parent_summary",
        lazy="noload",
        foreign_keys="[SummaryParentLink.parent_summary_id]",
    )

    __table_args__ = (
        Index("ix_summaries_category_status", "category_id", "compaction_status"),
        Index("ix_summaries_category_level", "category_id", "level"),
        Index("ix_summaries_level", "level"),
        Index("ix_summaries_status", "compaction_status"),
    )


class SummaryRawMemoryLink(Base):
    __tablename__ = "summary_raw_memory_links"

    summary_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("memory_summaries.id", ondelete="CASCADE"),
        primary_key=True,
    )
    raw_memory_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("raw_memories.id", ondelete="CASCADE"),
        primary_key=True,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")

    summary: Mapped[MemorySummary] = relationship(back_populates="raw_memory_links")
    raw_memory: Mapped[RawMemory] = relationship(back_populates="summary_links")

    __table_args__ = (
        Index("ix_srm_links_summary", "summary_id"),
        Index("ix_srm_links_raw", "raw_memory_id"),
    )


class SummaryParentLink(Base):
    __tablename__ = "summary_parent_links"

    summary_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("memory_summaries.id", ondelete="CASCADE"),
        primary_key=True,
    )
    parent_summary_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("memory_summaries.id", ondelete="CASCADE"),
        primary_key=True,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")

    summary: Mapped[MemorySummary] = relationship(
        back_populates="parent_links", foreign_keys=[summary_id]
    )
    parent_summary: Mapped[MemorySummary] = relationship(
        back_populates="child_links", foreign_keys=[parent_summary_id]
    )

    __table_args__ = (
        Index("ix_sp_links_summary", "summary_id"),
        Index("ix_sp_links_parent", "parent_summary_id"),
    )


class CompactionJob(Base, IdMixin):
    __tablename__ = "compaction_jobs"

    category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("memory_categories.id", ondelete="CASCADE"), nullable=False
    )
    source_type: Mapped[CompactionSourceType] = mapped_column(nullable=False)
    status: Mapped[JobStatus] = mapped_column(default=JobStatus.QUEUED, nullable=False)
    input_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    output_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    llm_model: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    prompt_version: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    error_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    started_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    finished_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    category: Mapped[MemoryCategory] = relationship(back_populates="compaction_jobs")

    __table_args__ = (
        Index("ix_jobs_category_status", "category_id", "status"),
        Index("ix_jobs_status", "status"),
    )


class DelegationGrant(Base, IdMixin):
    __tablename__ = "delegation_grants"

    conversation_scope: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    token_cap: Mapped[int] = mapped_column(Integer, nullable=False)
    expires_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_grants_expires", "expires_at"),
        Index("ix_grants_revoked", "revoked_at"),
    )
