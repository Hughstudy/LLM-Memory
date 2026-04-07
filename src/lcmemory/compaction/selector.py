from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from lcmemory.db.models import MemorySummary, RawMemory
from lcmemory.db.repositories.raw_memories import RawMemoryRepository
from lcmemory.db.repositories.summaries import SummaryRepository


class CompactionSelector:
    def __init__(self) -> None:
        self.raw_memory_repo = RawMemoryRepository()
        self.summary_repo = SummaryRepository()

    async def select_raw_batch(
        self, session: AsyncSession, category_id: uuid.UUID, limit: int = 15
    ) -> list[RawMemory]:
        return await self.raw_memory_repo.list_eligible_for_compaction(
            session, category_id, limit=limit
        )

    async def select_summary_batch(
        self, session: AsyncSession, category_id: uuid.UUID, level: int, limit: int = 15
    ) -> list[MemorySummary]:
        return await self.summary_repo.list_eligible_for_compaction(
            session, category_id, level, limit=limit
        )
