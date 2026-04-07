from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError

from lcmemory.db.repositories.categories import CategoryRepository


class FakeSession:
    def __init__(self) -> None:
        self.rolled_back = False

    async def rollback(self) -> None:
        self.rolled_back = True


async def test_get_or_create_recovers_from_integrity_error(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = CategoryRepository()
    session = FakeSession()
    expected = object()
    calls: list[str] = []

    async def fake_get_by_name(_session: FakeSession, name: str):
        calls.append(f"get:{name}")
        return None if len(calls) == 1 else expected

    async def fake_create(_session: FakeSession, **_: object):
        calls.append("create")
        raise IntegrityError("insert", {}, Exception("duplicate"))

    monkeypatch.setattr(repo, "get_by_name", fake_get_by_name)
    monkeypatch.setattr(repo, "create", fake_create)

    category = await repo.get_or_create(session, name="shared")

    assert category is expected
    assert session.rolled_back is True
    assert calls == ["get:shared", "create", "get:shared"]
