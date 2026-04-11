from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from lcmemory.domain.enums import SummaryKind
from lcmemory.domain.schemas import ExpandParams
from lcmemory.retrieval.expand import ExpandEngine


class FakeResult:
    def __init__(self, rows: list[tuple[Any, ...]] | None = None, scalar: Any = None) -> None:
        self._rows = rows or []
        self._scalar = scalar

    def fetchall(self) -> list[tuple[Any, ...]]:
        return self._rows

    def scalar_one_or_none(self) -> Any:
        return self._scalar


@dataclass
class FakeSummary:
    id: Any
    summary_text: str
    kind: SummaryKind


class FakeSession:
    def __init__(self, root_id: Any, parent_id: Any) -> None:
        self._root_id = root_id
        self._parent_id = parent_id

    async def __aenter__(self) -> FakeSession:
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        return None

    async def execute(self, query: Any, params: dict[str, Any] | None = None) -> FakeResult:
        query_text = str(query)
        if "FROM memory_summaries" in query_text:
            sid = self._extract_summary_id(query, params)
            if sid == self._root_id:
                return FakeResult(
                    scalar=FakeSummary(self._root_id, "Leaf summary about rotation", SummaryKind.LEAF)
                )
            if sid == self._parent_id:
                return FakeResult(
                    scalar=FakeSummary(
                        self._parent_id, "Parent condensed summary", SummaryKind.CONDENSED
                    )
                )
            return FakeResult(scalar=None)
        if "SELECT parent_summary_id FROM summary_parent_links" in query_text:
            if params is not None and params["id"] == self._root_id:
                return FakeResult(rows=[(self._parent_id,)])
            return FakeResult(rows=[])
        if "SELECT raw_memory_id FROM summary_raw_memory_links" in query_text:
            return FakeResult(rows=[])
        raise AssertionError(f"Unexpected query: {query_text}")

    @staticmethod
    def _extract_summary_id(query: Any, params: dict[str, Any] | None) -> Any:
        if params is not None and "id" in params:
            return params["id"]

        compile_fn = getattr(query, "compile", None)
        if callable(compile_fn):
            compiled = query.compile()
            for key in ("id", "id_1"):
                if key in compiled.params:
                    return compiled.params[key]

        return None


class FakeSessionFactory:
    def __init__(self, session: FakeSession) -> None:
        self._session = session

    def __call__(self) -> FakeSession:
        return self._session


async def test_expand_traverses_to_parent_summaries() -> None:
    root_id = uuid4()
    parent_id = uuid4()
    session = FakeSession(root_id, parent_id)
    engine = ExpandEngine(FakeSessionFactory(session))

    result = await engine.expand(
        ExpandParams(
            summary_ids=[str(root_id)],
            max_depth=1,
            include_messages=False,
            token_cap=1000,
        )
    )

    assert [item.id for item in result.items] == [str(root_id), str(parent_id)]
    assert [item.depth for item in result.items] == [0, 1]
