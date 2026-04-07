from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from lcmemory.config import Settings, get_settings
from lcmemory.db.models import RawMemory
from lcmemory.db.repositories.categories import CategoryRepository
from lcmemory.db.repositories.summaries import SummaryRepository
from lcmemory.domain.enums import CompactionStatus

if TYPE_CHECKING:
    from lcmemory.compaction.service import CompactionService
from lcmemory.domain.schemas import SummaryDTO


class CompactionWorker:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        settings: Settings | None = None,
    ):
        self._session_factory = session_factory
        self._settings = settings or get_settings()
        self._category_repo = CategoryRepository()
        self._summary_repo = SummaryRepository()
        self._compaction_service: CompactionService | None = None

    def _get_compaction_service(self) -> CompactionService:
        if self._compaction_service is None:
            from lcmemory.compaction.service import CompactionService

            self._compaction_service = CompactionService(self._session_factory, self._settings)
        return self._compaction_service

    async def check_and_compact(self, category_name: str) -> SummaryDTO | None:
        async with self._session_factory() as session:
            category = await self._category_repo.get_by_name(session, category_name)
            if category is None:
                return None

            count_result = await session.execute(
                select(func.count())
                .select_from(RawMemory)
                .where(RawMemory.category_id == category.id)
                .where(RawMemory.compaction_status == CompactionStatus.ACTIVE)
            )
            count = count_result.scalar() or 0

            if count >= self._settings.compaction_threshold:
                result = await self._get_compaction_service().compact_raw_batch(category.id)
                return result

            eligible_levels = await self._summary_repo.find_eligible_levels(
                session, category.id, self._settings.compaction_threshold
            )
            if eligible_levels:
                return await self._get_compaction_service().compact_summary_level(
                    category.id, eligible_levels[0]
                )

            return None

    async def check_all_categories(self) -> list[SummaryDTO]:
        async with self._session_factory() as session:
            categories = await self._category_repo.list_all(session)

        results: list[SummaryDTO] = []
        for category in categories:
            result = await self.check_and_compact(category.name)
            if result is not None:
                results.append(result)

        return results
