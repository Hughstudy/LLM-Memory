from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from lcmemory.db.models import MemorySummary, SummaryParentLink, SummaryRawMemoryLink
from lcmemory.domain.enums import CompactionStatus, SummaryKind


class SummaryRepository:
    async def create(
        self,
        session: AsyncSession,
        *,
        category_id: uuid.UUID,
        level: int,
        kind: SummaryKind,
        title: str | None,
        summary_text: str,
        fact_summary: str,
        comment_summary: str,
        behavior_summary: str,
        token_count: int,
        source_count: int,
        descendant_raw_count: int,
        metadata_json: dict[str, Any] | None = None,
    ) -> MemorySummary:
        summary = MemorySummary(
            category_id=category_id,
            level=level,
            kind=kind,
            title=title,
            summary_text=summary_text,
            fact_summary=fact_summary,
            comment_summary=comment_summary,
            behavior_summary=behavior_summary,
            token_count=token_count,
            source_count=source_count,
            descendant_raw_count=descendant_raw_count,
            metadata_json=metadata_json,
        )
        session.add(summary)
        await session.flush()
        await session.refresh(summary)
        return summary

    async def get_by_id(self, session: AsyncSession, summary_id: uuid.UUID) -> MemorySummary | None:
        result = await session.execute(select(MemorySummary).where(MemorySummary.id == summary_id))
        return result.scalar_one_or_none()

    async def list_by_category_and_level(
        self, session: AsyncSession, category_id: uuid.UUID, level: int
    ) -> list[MemorySummary]:
        result = await session.execute(
            select(MemorySummary)
            .where(MemorySummary.category_id == category_id, MemorySummary.level == level)
            .order_by(MemorySummary.created_at.desc())
        )
        return list(result.scalars().all())

    async def list_active_by_category_and_level(
        self, session: AsyncSession, category_id: uuid.UUID, level: int
    ) -> list[MemorySummary]:
        result = await session.execute(
            select(MemorySummary)
            .where(
                MemorySummary.category_id == category_id,
                MemorySummary.level == level,
                MemorySummary.compaction_status == CompactionStatus.ACTIVE,
            )
            .order_by(MemorySummary.created_at.desc())
        )
        return list(result.scalars().all())

    async def count_active_by_category_and_level(
        self, session: AsyncSession, category_id: uuid.UUID, level: int
    ) -> int:
        result = await session.execute(
            select(func.count())
            .select_from(MemorySummary)
            .where(
                MemorySummary.category_id == category_id,
                MemorySummary.level == level,
                MemorySummary.compaction_status == CompactionStatus.ACTIVE,
            )
        )
        return result.scalar_one()

    async def mark_superseded(self, session: AsyncSession, summary_ids: list[uuid.UUID]) -> None:
        await session.execute(
            update(MemorySummary)
            .where(MemorySummary.id.in_(summary_ids))
            .values(compaction_status=CompactionStatus.SUPERSEDED)
        )

    async def mark_batched(
        self,
        session: AsyncSession,
        summary_ids: list[uuid.UUID],
        batch_id: uuid.UUID,
    ) -> None:
        await session.execute(
            update(MemorySummary)
            .where(MemorySummary.id.in_(summary_ids))
            .values(
                compaction_status=CompactionStatus.BATCHED,
                compaction_batch_id=batch_id,
            )
        )

    async def mark_active(self, session: AsyncSession, summary_ids: list[uuid.UUID]) -> None:
        await session.execute(
            update(MemorySummary)
            .where(MemorySummary.id.in_(summary_ids))
            .values(
                compaction_status=CompactionStatus.ACTIVE,
                compaction_batch_id=None,
            )
        )

    async def mark_superseded_with_batch(
        self,
        session: AsyncSession,
        summary_ids: list[uuid.UUID],
        batch_id: uuid.UUID,
    ) -> None:
        await session.execute(
            update(MemorySummary)
            .where(MemorySummary.id.in_(summary_ids))
            .values(
                compaction_status=CompactionStatus.SUPERSEDED,
                compaction_batch_id=batch_id,
            )
        )

    async def find_eligible_levels(
        self,
        session: AsyncSession,
        category_id: uuid.UUID,
        threshold: int,
    ) -> list[int]:
        result = await session.execute(
            select(MemorySummary.level)
            .where(
                MemorySummary.category_id == category_id,
                MemorySummary.compaction_status == CompactionStatus.ACTIVE,
            )
            .group_by(MemorySummary.level)
            .having(func.count() >= threshold)
            .order_by(MemorySummary.level.asc())
        )
        return list(result.scalars().all())

    async def add_raw_memory_links(
        self,
        session: AsyncSession,
        summary_id: uuid.UUID,
        raw_memory_ids: list[uuid.UUID],
    ) -> None:
        for position, raw_memory_id in enumerate(raw_memory_ids):
            link = SummaryRawMemoryLink(
                summary_id=summary_id,
                raw_memory_id=raw_memory_id,
                position=position,
            )
            session.add(link)
        await session.flush()

    async def add_parent_links(
        self,
        session: AsyncSession,
        summary_id: uuid.UUID,
        parent_summary_ids: list[uuid.UUID],
    ) -> None:
        for position, parent_summary_id in enumerate(parent_summary_ids):
            link = SummaryParentLink(
                summary_id=summary_id,
                parent_summary_id=parent_summary_id,
                position=position,
            )
            session.add(link)
        await session.flush()

    async def get_parent_ids(self, session: AsyncSession, summary_id: uuid.UUID) -> list[uuid.UUID]:
        result = await session.execute(
            select(SummaryParentLink.parent_summary_id)
            .where(SummaryParentLink.summary_id == summary_id)
            .order_by(SummaryParentLink.position)
        )
        return list(result.scalars().all())

    async def get_child_ids(self, session: AsyncSession, summary_id: uuid.UUID) -> list[uuid.UUID]:
        result = await session.execute(
            select(SummaryParentLink.summary_id)
            .where(SummaryParentLink.parent_summary_id == summary_id)
            .order_by(SummaryParentLink.position)
        )
        return list(result.scalars().all())

    async def get_raw_memory_ids(
        self, session: AsyncSession, summary_id: uuid.UUID
    ) -> list[uuid.UUID]:
        result = await session.execute(
            select(SummaryRawMemoryLink.raw_memory_id)
            .where(SummaryRawMemoryLink.summary_id == summary_id)
            .order_by(SummaryRawMemoryLink.position)
        )
        return list(result.scalars().all())
