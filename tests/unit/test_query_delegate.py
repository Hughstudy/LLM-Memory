from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from lcmemory.domain.schemas import ExpandItem, ExpandResult, GrepResult, MemorySnippet
from lcmemory.retrieval.query_delegate import QueryDelegate


class FakeResult:
    def __init__(self, value: Any):
        self._value = value

    def scalar_one_or_none(self) -> Any:
        return self._value


class FakeSession:
    def __init__(self) -> None:
        self.grant: Any = None

    async def __aenter__(self) -> FakeSession:
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        return None

    def add(self, value: Any) -> None:
        self.grant = value

    async def commit(self) -> None:
        return None

    async def execute(self, _query: Any) -> FakeResult:
        return FakeResult(self.grant)


class FakeSessionFactory:
    def __init__(self) -> None:
        self.session = FakeSession()

    def __call__(self) -> FakeSession:
        return self.session


class FakeGrepEngine:
    async def grep(self, _params: Any) -> GrepResult:
        return GrepResult(
            items=[
                MemorySnippet(
                    id=str(uuid4()),
                    node_type="summary",
                    category="project_state",
                    level=0,
                    snippet="Leaf summary about refresh tokens",
                ),
                MemorySnippet(
                    id=str(uuid4()),
                    node_type="raw_memory",
                    category="project_state",
                    snippet="Rotate refresh tokens on every refresh",
                ),
            ],
            total=2,
        )


class FakeDescribeEngine:
    async def describe(self, _summary_id: Any) -> None:
        return None


class FakeExpandEngine:
    async def expand(self, _params: Any) -> ExpandResult:
        return ExpandResult(
            items=[
                ExpandItem(
                    id="sum-1",
                    node_type="summary",
                    depth=0,
                    content="Refresh tokens are rotated and audited.",
                ),
                ExpandItem(
                    id="raw-1",
                    node_type="raw_memory",
                    depth=1,
                    content="Rotate the token pair on every refresh.",
                    fact="Rotate the token pair.",
                    comment="Prevents replay abuse.",
                    behavior="Always replace the old refresh token.",
                ),
            ],
            truncated=False,
            used_tokens=42,
        )


@dataclass
class ExpiredGrant:
    revoked_at: datetime | None
    expires_at: datetime
    token_cap: int


async def test_expand_query_creates_answer_and_revokes_grant() -> None:
    session_factory = FakeSessionFactory()
    delegate = QueryDelegate(
        session_factory,
        FakeGrepEngine(),
        FakeDescribeEngine(),
        FakeExpandEngine(),
    )

    result = await delegate.expand_query(
        "refresh token",
        "Find the agreed refresh-token behavior",
        max_expand_tokens=120,
        ttl_seconds=60,
    )

    assert "Find the agreed refresh-token behavior" in result.answer
    assert "sum-1" in result.cited_ids
    assert result.total_source_tokens == 42
    assert session_factory.session.grant is not None
    assert session_factory.session.grant.revoked_at is not None


async def test_validate_grant_rejects_expired_grant() -> None:
    session_factory = FakeSessionFactory()
    session_factory.session.grant = ExpiredGrant(
        revoked_at=None,
        expires_at=datetime.now(UTC) - timedelta(seconds=1),
        token_cap=10,
    )
    delegate = QueryDelegate(
        session_factory,
        FakeGrepEngine(),
        FakeDescribeEngine(),
        FakeExpandEngine(),
    )

    try:
        await delegate._validate_grant(uuid4())
    except ValueError as exc:
        assert "expired" in str(exc)
    else:
        raise AssertionError("Expected expired grant validation to fail")
