from __future__ import annotations

from typing import Any, cast

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from lcmemory.db.models import MemoryCategory, MemorySummary, RawMemory
from lcmemory.domain.enums import NodeType, SearchMode, SearchScope
from lcmemory.domain.schemas import GrepParams, GrepResult, MemorySnippet


class GrepEngine:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self._session_factory = session_factory

    async def grep(self, params: GrepParams) -> GrepResult:
        async with self._session_factory() as session:
            items: list[MemorySnippet] = []
            pattern = params.pattern
            mode = params.mode
            scope = params.scope
            category = params.category
            limit = params.limit
            total = 0

            if scope in (SearchScope.MESSAGES, SearchScope.BOTH):
                total += await self._count_messages(session, pattern, mode, category)
                messages_items = await self._search_messages(
                    session, pattern, mode, category, limit
                )
                items.extend(messages_items)

            if scope in (SearchScope.SUMMARIES, SearchScope.BOTH):
                total += await self._count_summaries(session, pattern, mode, category)
                summaries_items = await self._search_summaries(
                    session, pattern, mode, category, limit
                )
                items.extend(summaries_items)

            items = items[:limit]
            return GrepResult(items=items, total=total)

    async def _count_messages(
        self,
        session: AsyncSession,
        pattern: str,
        mode: SearchMode,
        category: str | None,
    ) -> int:
        query = (
            select(func.count())
            .select_from(RawMemory)
            .join(MemoryCategory, RawMemory.category_id == MemoryCategory.id)
        )
        query = self._apply_message_filters(query, pattern, mode, category)
        result = await session.execute(query)
        return cast(int, result.scalar_one())

    async def _count_summaries(
        self,
        session: AsyncSession,
        pattern: str,
        mode: SearchMode,
        category: str | None,
    ) -> int:
        query = (
            select(func.count())
            .select_from(MemorySummary)
            .join(MemoryCategory, MemorySummary.category_id == MemoryCategory.id)
        )
        query = self._apply_summary_filters(query, pattern, mode, category)
        result = await session.execute(query)
        return cast(int, result.scalar_one())

    async def _search_messages(
        self,
        session: AsyncSession,
        pattern: str,
        mode: SearchMode,
        category: str | None,
        limit: int,
    ) -> list[MemorySnippet]:
        query = (
            select(RawMemory, MemoryCategory.name)
            .select_from(RawMemory)
            .join(MemoryCategory, RawMemory.category_id == MemoryCategory.id)
        )
        query = self._apply_message_filters(query, pattern, mode, category)
        query = query.order_by(RawMemory.created_at.desc()).limit(limit)
        result = await session.execute(query)
        rows = result.all()

        items: list[MemorySnippet] = []
        for row in rows:
            raw_memory, cat_name = row
            items.append(
                MemorySnippet(
                    id=str(raw_memory.id),
                    node_type=NodeType.RAW_MEMORY,
                    category=cat_name,
                    created_at=raw_memory.created_at,
                    snippet=raw_memory.content_text[:200],
                )
            )
        return items

    async def _search_summaries(
        self,
        session: AsyncSession,
        pattern: str,
        mode: SearchMode,
        category: str | None,
        limit: int,
    ) -> list[MemorySnippet]:
        query = (
            select(MemorySummary, MemoryCategory.name)
            .select_from(MemorySummary)
            .join(MemoryCategory, MemorySummary.category_id == MemoryCategory.id)
        )
        query = self._apply_summary_filters(query, pattern, mode, category)
        query = query.order_by(MemorySummary.created_at.desc()).limit(limit)
        result = await session.execute(query)
        rows = result.all()

        items: list[MemorySnippet] = []
        for row in rows:
            summary, cat_name = row
            items.append(
                MemorySnippet(
                    id=str(summary.id),
                    node_type=NodeType.SUMMARY,
                    category=cat_name,
                    level=summary.level,
                    created_at=summary.created_at,
                    snippet=summary.summary_text[:200],
                )
            )
        return items

    def _apply_message_filters(
        self,
        query: Any,
        pattern: str,
        mode: SearchMode,
        category: str | None,
    ) -> Any:
        if mode == SearchMode.FULL_TEXT:
            query = query.where(
                text("raw_memories.content_text @@ plainto_tsquery('english', :query)")
            )
            query = query.params(query=pattern)
        else:
            query = query.where(RawMemory.content_text.ilike(f"%{pattern}%"))

        if category:
            query = query.where(MemoryCategory.name == category)

        return query

    def _apply_summary_filters(
        self,
        query: Any,
        pattern: str,
        mode: SearchMode,
        category: str | None,
    ) -> Any:
        if mode == SearchMode.FULL_TEXT:
            query = query.where(
                text("memory_summaries.summary_text @@ plainto_tsquery('english', :query)")
            )
            query = query.params(query=pattern)
        else:
            query = query.where(MemorySummary.summary_text.ilike(f"%{pattern}%"))

        if category:
            query = query.where(MemoryCategory.name == category)

        return query
