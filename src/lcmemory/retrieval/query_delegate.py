from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from lcmemory.db.models import DelegationGrant
from lcmemory.domain.schemas import (
    ExpandItem,
    ExpandParams,
    ExpandQueryResult,
    ExpandResult,
    GrepParams,
    GrepResult,
    MemorySnippet,
)

if TYPE_CHECKING:
    from lcmemory.retrieval.describe import DescribeEngine
    from lcmemory.retrieval.expand import ExpandEngine
    from lcmemory.retrieval.grep import GrepEngine


class QueryDelegate:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        grep_engine: GrepEngine,
        describe_engine: DescribeEngine,
        expand_engine: ExpandEngine,
    ):
        self._session_factory = session_factory
        self._grep_engine = grep_engine
        self._describe_engine = describe_engine
        self._expand_engine = expand_engine

    async def expand_query(
        self,
        query: str,
        prompt: str,
        *,
        max_expand_tokens: int = 16000,
        ttl_seconds: int = 300,
    ) -> ExpandQueryResult:
        grant_id = uuid.uuid4()
        async with self._session_factory() as session:
            grant = DelegationGrant(
                id=grant_id,
                conversation_scope={"query": query, "prompt": prompt},
                token_cap=max_expand_tokens,
                expires_at=datetime.now(UTC) + timedelta(seconds=ttl_seconds),
            )
            session.add(grant)
            await session.commit()

        try:
            return await self._spawn_sub_agent(grant_id, query, prompt)
        finally:
            await self._revoke_grant(grant_id)

    async def _spawn_sub_agent(
        self, grant_id: uuid.UUID, query: str, prompt: str
    ) -> ExpandQueryResult:
        grant = await self._validate_grant(grant_id)
        grep_result: GrepResult = await self._grep_engine.grep(GrepParams(pattern=query, limit=10))

        summary_ids = [item.id for item in grep_result.items if item.node_type == "summary"][:3]

        expand_result = ExpandResult(items=[], truncated=False, used_tokens=0)
        if summary_ids:
            expand_result = await self._expand_engine.expand(
                ExpandParams(
                    summary_ids=summary_ids,
                    max_depth=2,
                    include_messages=True,
                    token_cap=grant.token_cap,
                )
            )

        answer = self._build_answer(query, prompt, grep_result.items, expand_result.items)
        cited_ids = self._collect_citations(grep_result.items, expand_result.items)

        return ExpandQueryResult(
            answer=answer,
            cited_ids=cited_ids,
            expanded_summary_count=len(summary_ids),
            total_source_tokens=expand_result.used_tokens,
            truncated=expand_result.truncated,
        )

    async def _validate_grant(self, grant_id: uuid.UUID) -> DelegationGrant:
        async with self._session_factory() as session:
            result = await session.execute(
                select(DelegationGrant).where(DelegationGrant.id == grant_id)
            )
            grant = result.scalar_one_or_none()

        if grant is None:
            raise ValueError(f"Grant {grant_id} not found")
        if grant.revoked_at is not None:
            raise ValueError(f"Grant {grant_id} has been revoked")
        if grant.expires_at <= datetime.now(UTC):
            raise ValueError(f"Grant {grant_id} has expired")
        return grant

    async def _revoke_grant(self, grant_id: uuid.UUID) -> None:
        async with self._session_factory() as session:
            result = await session.execute(
                select(DelegationGrant).where(DelegationGrant.id == grant_id)
            )
            grant = result.scalar_one_or_none()
            if grant is None or grant.revoked_at is not None:
                return
            grant.revoked_at = datetime.now(UTC)
            await session.commit()

    def _build_answer(
        self,
        query: str,
        prompt: str,
        snippets: list[MemorySnippet],
        expanded_items: list[ExpandItem],
    ) -> str:
        if expanded_items:
            evidence_lines = [f"- [{item.id}] {item.content}" for item in expanded_items[:8]]
            return f"Prompt: {prompt}\n\nRelevant evidence:\n" + "\n".join(evidence_lines)

        if snippets:
            snippet_lines = [f"- [{item.id}] {item.snippet}" for item in snippets[:5]]
            return f"Prompt: {prompt}\n\nTop matches:\n" + "\n".join(snippet_lines)

        return f"No results found for query: {query}"

    def _collect_citations(
        self,
        snippets: list[MemorySnippet],
        expanded_items: list[ExpandItem],
    ) -> list[str]:
        ordered_ids: list[str] = []
        for item_id in [item.id for item in expanded_items] + [item.id for item in snippets]:
            if item_id not in ordered_ids:
                ordered_ids.append(item_id)
        return ordered_ids
