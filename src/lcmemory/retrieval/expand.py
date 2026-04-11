from __future__ import annotations

import uuid

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from lcmemory.db.models import MemorySummary, RawMemory
from lcmemory.domain.enums import NodeType, SummaryKind
from lcmemory.domain.schemas import ExpandItem, ExpandParams, ExpandResult


class ExpandEngine:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self._session_factory = session_factory

    async def expand(self, params: ExpandParams) -> ExpandResult:
        async with self._session_factory() as session:
            items: list[ExpandItem] = []
            visited: set[uuid.UUID] = set()
            used_tokens_ref = [0]
            truncated_ref = [False]

            for sid_str in params.summary_ids:
                if truncated_ref[0]:
                    break
                sid = uuid.UUID(sid_str)
                await self._expand_summary(
                    session,
                    sid,
                    depth=0,
                    max_depth=params.max_depth,
                    include_messages=params.include_messages,
                    token_cap=params.token_cap,
                    items=items,
                    visited=visited,
                    used_tokens_ref=used_tokens_ref,
                    truncated_ref=truncated_ref,
                )

            return ExpandResult(
                items=items,
                truncated=truncated_ref[0],
                used_tokens=used_tokens_ref[0],
            )

    async def _expand_summary(
        self,
        session: AsyncSession,
        summary_id: uuid.UUID,
        depth: int,
        max_depth: int,
        include_messages: bool,
        token_cap: int,
        items: list[ExpandItem],
        visited: set[uuid.UUID],
        used_tokens_ref: list[int],
        truncated_ref: list[bool],
    ) -> None:
        if summary_id in visited:
            return
        if truncated_ref[0]:
            return

        visited.add(summary_id)

        result = await session.execute(select(MemorySummary).where(MemorySummary.id == summary_id))
        summary = result.scalar_one_or_none()
        if summary is None:
            return

        content = summary.summary_text
        token_estimate = len(content) // 4
        if used_tokens_ref[0] + token_estimate > token_cap:
            truncated_ref[0] = True
            return

        used_tokens_ref[0] += token_estimate
        items.append(
            ExpandItem(
                id=str(summary.id),
                node_type=NodeType.SUMMARY,
                depth=depth,
                content=content,
            )
        )

        parent_result = await session.execute(
            text("SELECT parent_summary_id FROM summary_parent_links WHERE summary_id = :id"),
            {"id": summary_id},
        )
        parent_ids = [row[0] for row in parent_result.fetchall()]

        if depth < max_depth:
            for parent_id in parent_ids:
                if truncated_ref[0]:
                    break
                await self._expand_summary(
                    session,
                    parent_id,
                    depth + 1,
                    max_depth,
                    include_messages,
                    token_cap,
                    items,
                    visited,
                    used_tokens_ref,
                    truncated_ref,
                )

        if include_messages and summary.kind == SummaryKind.LEAF:
            raw_result = await session.execute(
                text("SELECT raw_memory_id FROM summary_raw_memory_links WHERE summary_id = :id"),
                {"id": summary_id},
            )
            raw_ids = [row[0] for row in raw_result.fetchall()]

            for raw_id in raw_ids:
                if truncated_ref[0]:
                    break
                raw_mem_result = await session.execute(
                    select(RawMemory).where(RawMemory.id == raw_id)
                )
                raw_mem = raw_mem_result.scalar_one_or_none()
                if raw_mem is None:
                    continue

                raw_content = f"{raw_mem.fact} {raw_mem.comment} {raw_mem.behavior}"
                raw_token_estimate = len(raw_content) // 4
                if used_tokens_ref[0] + raw_token_estimate > token_cap:
                    truncated_ref[0] = True
                    break

                used_tokens_ref[0] += raw_token_estimate
                items.append(
                    ExpandItem(
                        id=str(raw_mem.id),
                        node_type=NodeType.RAW_MEMORY,
                        depth=depth + 1,
                        content=raw_content,
                        fact=raw_mem.fact,
                        comment=raw_mem.comment,
                        behavior=raw_mem.behavior,
                    )
                )
