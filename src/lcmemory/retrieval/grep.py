from __future__ import annotations

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from lcmemory.db.models import MemoryCategory, MemorySummary, RawMemory
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

            if scope in ("messages", "both"):
                messages_items = await self._search_messages(
                    session, pattern, mode, category, limit
                )
                items.extend(messages_items)

            if scope in ("summaries", "both"):
                summaries_items = await self._search_summaries(
                    session, pattern, mode, category, limit
                )
                items.extend(summaries_items)

            items = items[:limit]
            return GrepResult(items=items, total=len(items))

    async def _search_messages(
        self,
        session: AsyncSession,
        pattern: str,
        mode: str,
        category: str | None,
        limit: int,
    ) -> list[MemorySnippet]:
        if mode == "full_text":
            query = (
                select(RawMemory, MemoryCategory.name)
                .select_from(RawMemory)
                .join(MemoryCategory, RawMemory.category_id == MemoryCategory.id)
                .where(text("raw_memories.content_text @@ plainto_tsquery('english', :query)"))
                .params(query=pattern)
            )
        else:
            query = (
                select(RawMemory, MemoryCategory.name)
                .select_from(RawMemory)
                .join(MemoryCategory, RawMemory.category_id == MemoryCategory.id)
                .where(RawMemory.content_text.ilike(f"%{pattern}%"))
            )

        if category:
            query = query.where(MemoryCategory.name == category)

        query = query.order_by(RawMemory.created_at.desc()).limit(limit)
        result = await session.execute(query)
        rows = result.all()

        items: list[MemorySnippet] = []
        for row in rows:
            raw_memory, cat_name = row
            items.append(
                MemorySnippet(
                    id=str(raw_memory.id),
                    node_type="raw_memory",
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
        mode: str,
        category: str | None,
        limit: int,
    ) -> list[MemorySnippet]:
        if mode == "full_text":
            query = (
                select(MemorySummary, MemoryCategory.name)
                .select_from(MemorySummary)
                .join(MemoryCategory, MemorySummary.category_id == MemoryCategory.id)
                .where(text("memory_summaries.summary_text @@ plainto_tsquery('english', :query)"))
                .params(query=pattern)
            )
        else:
            query = (
                select(MemorySummary, MemoryCategory.name)
                .select_from(MemorySummary)
                .join(MemoryCategory, MemorySummary.category_id == MemoryCategory.id)
                .where(MemorySummary.summary_text.ilike(f"%{pattern}%"))
            )

        if category:
            query = query.where(MemoryCategory.name == category)

        query = query.order_by(MemorySummary.created_at.desc()).limit(limit)
        result = await session.execute(query)
        rows = result.all()

        items: list[MemorySnippet] = []
        for row in rows:
            summary, cat_name = row
            items.append(
                MemorySnippet(
                    id=str(summary.id),
                    node_type="summary",
                    category=cat_name,
                    level=summary.level,
                    created_at=summary.created_at,
                    snippet=summary.summary_text[:200],
                )
            )
        return items
