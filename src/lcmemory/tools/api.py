from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from lcmemory.config import Settings
from lcmemory.domain.schemas import (
    DescribeResult,
    ExpandParams,
    ExpandQueryResult,
    ExpandResult,
    GrepParams,
    GrepResult,
)
from lcmemory.retrieval.describe import DescribeEngine
from lcmemory.retrieval.expand import ExpandEngine
from lcmemory.retrieval.grep import GrepEngine
from lcmemory.retrieval.query_delegate import QueryDelegate
from lcmemory.tools.contracts import TOOL_DEFINITIONS, ToolDefinition


class ToolRegistry:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        settings: Settings | None = None,
    ):
        self._session_factory = session_factory
        self._settings = settings
        self._grep_engine: GrepEngine | None = None
        self._describe_engine: DescribeEngine | None = None
        self._expand_engine: ExpandEngine | None = None
        self._query_delegate: QueryDelegate | None = None

    def _get_grep_engine(self) -> GrepEngine:
        if self._grep_engine is None:
            self._grep_engine = GrepEngine(self._session_factory)
        return self._grep_engine

    def _get_describe_engine(self) -> DescribeEngine:
        if self._describe_engine is None:
            self._describe_engine = DescribeEngine(self._session_factory)
        return self._describe_engine

    def _get_expand_engine(self) -> ExpandEngine:
        if self._expand_engine is None:
            self._expand_engine = ExpandEngine(self._session_factory)
        return self._expand_engine

    def _get_query_delegate(self) -> QueryDelegate:
        if self._query_delegate is None:
            self._query_delegate = QueryDelegate(
                self._session_factory,
                self._get_grep_engine(),
                self._get_describe_engine(),
                self._get_expand_engine(),
            )
        return self._query_delegate

    async def call(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if tool_name == "lcm_grep":
            grep_params = GrepParams(**arguments)
            grep_result: GrepResult = await self._get_grep_engine().grep(grep_params)
            return grep_result.model_dump()

        if tool_name == "lcm_describe":
            summary_id = uuid.UUID(arguments["id"])
            describe_result: DescribeResult = await self._get_describe_engine().describe(summary_id)
            return describe_result.model_dump()

        if tool_name == "lcm_expand":
            expand_params = ExpandParams(**arguments)
            expand_result: ExpandResult = await self._get_expand_engine().expand(expand_params)
            return expand_result.model_dump()

        if tool_name == "lcm_expand_query":
            query = arguments["query"]
            prompt = arguments["prompt"]
            max_expand_tokens = arguments.get("max_expand_tokens", 16000)
            ttl_seconds = arguments.get("ttl_seconds", 300)
            expand_query_result: ExpandQueryResult = await self._get_query_delegate().expand_query(
                query,
                prompt,
                max_expand_tokens=max_expand_tokens,
                ttl_seconds=ttl_seconds,
            )
            return expand_query_result.model_dump()

        raise ValueError(f"Unknown tool: {tool_name}")

    def list_tools(self) -> list[ToolDefinition]:
        return TOOL_DEFINITIONS
