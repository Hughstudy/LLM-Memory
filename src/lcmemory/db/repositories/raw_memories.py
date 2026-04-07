from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from lcmemory.db.models import RawMemory
from lcmemory.domain.enums import CompactionStatus


class RawMemoryRepository:
    async def create(
        self,
        session: AsyncSession,
        *,
        category_id: uuid.UUID,
        fact: str,
        comment: str,
        behavior: str,
        content_text: str,
        token_count: int,
        metadata_json: dict[str, Any] | None = None,
    ) -> RawMemory:
        raw_memory = RawMemory(
            category_id=category_id,
            fact=fact,
            comment=comment,
            behavior=behavior,
            content_text=content_text,
            token_count=token_count,
            metadata_json=metadata_json,
        )
        session.add(raw_memory)
        await session.flush()
        await session.refresh(raw_memory)
        return raw_memory

    async def get_by_id(self, session: AsyncSession, memory_id: uuid.UUID) -> RawMemory | None:
        result = await session.execute(select(RawMemory).where(RawMemory.id == memory_id))
        return result.scalar_one_or_none()

    async def list_by_category(
        self,
        session: AsyncSession,
        category_id: uuid.UUID,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[RawMemory]:
        result = await session.execute(
            select(RawMemory)
            .where(RawMemory.category_id == category_id)
            .order_by(RawMemory.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def list_active_by_category(
        self,
        session: AsyncSession,
        category_id: uuid.UUID,
        *,
        limit: int = 50,
    ) -> list[RawMemory]:
        result = await session.execute(
            select(RawMemory)
            .where(
                RawMemory.category_id == category_id,
                RawMemory.compaction_status == CompactionStatus.ACTIVE,
            )
            .order_by(RawMemory.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def count_active_by_category(self, session: AsyncSession, category_id: uuid.UUID) -> int:
        from sqlalchemy import func

        result = await session.execute(
            select(func.count())
            .select_from(RawMemory)
            .where(
                RawMemory.category_id == category_id,
                RawMemory.compaction_status == CompactionStatus.ACTIVE,
            )
        )
        return result.scalar_one()

    async def list_eligible_for_compaction(
        self,
        session: AsyncSession,
        category_id: uuid.UUID,
        *,
        limit: int = 15,
    ) -> list[RawMemory]:
        result = await session.execute(
            select(RawMemory)
            .where(
                RawMemory.category_id == category_id,
                RawMemory.compaction_status == CompactionStatus.ACTIVE,
            )
            .order_by(RawMemory.created_at.asc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def mark_compacted(
        self,
        session: AsyncSession,
        memory_ids: list[uuid.UUID],
        batch_id: uuid.UUID,
    ) -> None:
        await session.execute(
            update(RawMemory)
            .where(RawMemory.id.in_(memory_ids))
            .values(
                compaction_status=CompactionStatus.COMPACTED,
                compaction_batch_id=batch_id,
            )
        )

    async def mark_batched(
        self,
        session: AsyncSession,
        memory_ids: list[uuid.UUID],
        batch_id: uuid.UUID,
    ) -> None:
        await session.execute(
            update(RawMemory)
            .where(RawMemory.id.in_(memory_ids))
            .values(
                compaction_status=CompactionStatus.BATCHED,
                compaction_batch_id=batch_id,
            )
        )

    async def mark_active(self, session: AsyncSession, memory_ids: list[uuid.UUID]) -> None:
        await session.execute(
            update(RawMemory)
            .where(RawMemory.id.in_(memory_ids))
            .values(
                compaction_status=CompactionStatus.ACTIVE,
                compaction_batch_id=None,
            )
        )
