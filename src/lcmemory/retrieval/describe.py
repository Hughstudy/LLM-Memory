from __future__ import annotations

import uuid

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from lcmemory.db.models import MemorySummary
from lcmemory.domain.schemas import (
    DescribeResult,
    SubtreeNode,
    SummaryDTO,
)


class DescribeEngine:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self._session_factory = session_factory

    async def describe(self, summary_id: uuid.UUID) -> DescribeResult:
        async with self._session_factory() as session:
            result = await session.execute(
                select(MemorySummary).where(MemorySummary.id == summary_id)
            )
            summary = result.scalar_one_or_none()
            if summary is None:
                raise ValueError(f"Summary {summary_id} not found")

            parent_ids = await self._fetch_parent_ids(session, summary_id)
            child_ids = await self._fetch_child_ids(session, summary_id)
            raw_memory_ids = await self._fetch_raw_memory_ids(session, summary_id)
            subtree = await self._fetch_subtree_manifest(session, summary_id)

            return DescribeResult(
                summary=SummaryDTO.model_validate(summary),
                parents=[str(pid) for pid in parent_ids],
                children=[str(cid) for cid in child_ids],
                source_raw_memory_ids=[str(rid) for rid in raw_memory_ids],
                subtree=subtree,
            )

    async def _fetch_parent_ids(
        self, session: AsyncSession, summary_id: uuid.UUID
    ) -> list[uuid.UUID]:
        result = await session.execute(
            text("SELECT parent_summary_id FROM summary_parent_links WHERE summary_id = :id"),
            {"id": summary_id},
        )
        return [row[0] for row in result.fetchall()]

    async def _fetch_child_ids(
        self, session: AsyncSession, summary_id: uuid.UUID
    ) -> list[uuid.UUID]:
        result = await session.execute(
            text("SELECT summary_id FROM summary_parent_links WHERE parent_summary_id = :id"),
            {"id": summary_id},
        )
        return [row[0] for row in result.fetchall()]

    async def _fetch_raw_memory_ids(
        self, session: AsyncSession, summary_id: uuid.UUID
    ) -> list[uuid.UUID]:
        result = await session.execute(
            text("SELECT raw_memory_id FROM summary_raw_memory_links WHERE summary_id = :id"),
            {"id": summary_id},
        )
        return [row[0] for row in result.fetchall()]

    async def _fetch_subtree_manifest(
        self, session: AsyncSession, summary_id: uuid.UUID
    ) -> list[SubtreeNode]:
        query = text("""
            WITH RECURSIVE subtree AS (
                 SELECT summary_id, parent_summary_id,
                        0 as depth_from_root,
                        '' as path,
                        ARRAY[summary_id]::uuid[] as visited_ids
                 FROM summary_parent_links WHERE summary_id = :id
                 UNION ALL
                 SELECT sp.summary_id, sp.parent_summary_id,
                        s.depth_from_root + 1,
                        s.path || '>' || sp.summary_id::text,
                        array_append(s.visited_ids, sp.summary_id)
                 FROM summary_parent_links sp
                 JOIN subtree s ON sp.parent_summary_id = s.summary_id
                 WHERE NOT sp.summary_id = ANY(s.visited_ids)
            )
            SELECT ms.id,
                   COALESCE(sub.depth_from_root, 0) as depth_from_root,
                   COALESCE(sub.path, '') as path,
                   (SELECT COUNT(*)
                    FROM summary_parent_links
                    WHERE parent_summary_id = ms.id) as child_count,
                   ms.descendant_raw_count, ms.token_count
            FROM memory_summaries ms
            LEFT JOIN subtree sub ON ms.id = sub.summary_id
            WHERE ms.id = :id
               OR ms.id IN (SELECT summary_id FROM subtree)
            ORDER BY COALESCE(sub.depth_from_root, 0)
        """)
        result = await session.execute(query, {"id": summary_id})
        rows = result.fetchall()

        nodes: list[SubtreeNode] = []
        for row in rows:
            nodes.append(
                SubtreeNode(
                    id=str(row[0]),
                    depth_from_root=row[1],
                    path=row[2] or "",
                    child_count=row[3],
                    descendant_raw_count=row[4],
                    token_count=row[5],
                )
            )
        return nodes
