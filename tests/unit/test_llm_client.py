from __future__ import annotations

import json

import httpx
import pytest

from lcmemory.compaction.llm_client import LLMClient
from lcmemory.config import Settings


class FakeResponse:
    def __init__(
        self,
        *,
        content: str,
        status_code: int = 200,
        headers: dict[str, str] | None = None,
    ) -> None:
        self._content = content
        self.status_code = status_code
        self.headers = headers or {}
        self.request = httpx.Request("POST", "https://example.test/chat/completions")

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                "request failed",
                request=self.request,
                response=httpx.Response(self.status_code, request=self.request),
            )

    def json(self) -> dict[str, object]:
        return {"choices": [{"message": {"content": self._content}}]}


def build_client() -> LLMClient:
    settings = Settings(LCM_LLM_API_KEY="test-key")
    return LLMClient(settings, max_retries=3)


async def test_summarize_rejects_missing_required_fields() -> None:
    client = build_client()

    async def fake_post(*args: object, **kwargs: object) -> FakeResponse:
        return FakeResponse(content=json.dumps({"title": "ok"}))

    client._client.post = fake_post

    with pytest.raises(ValueError, match="required summary schema"):
        await client.summarize([{"role": "user", "content": "hello"}])


async def test_summarize_retries_rate_limits(monkeypatch: pytest.MonkeyPatch) -> None:
    client = build_client()
    calls = 0
    sleeps: list[float] = []

    async def fake_post(*args: object, **kwargs: object) -> FakeResponse:
        nonlocal calls
        calls += 1
        if calls == 1:
            return FakeResponse(content="{}", status_code=429, headers={"Retry-After": "1.5"})
        return FakeResponse(
            content=json.dumps(
                {
                    "title": "Title",
                    "summary_text": "Summary",
                    "fact_summary": "Fact",
                    "comment_summary": "Comment",
                    "behavior_summary": "Behavior",
                }
            )
        )

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    client._client.post = fake_post
    monkeypatch.setattr("lcmemory.compaction.llm_client.asyncio.sleep", fake_sleep)

    result = await client.summarize([{"role": "user", "content": "hello"}])

    assert result["title"] == "Title"
    assert calls == 2
    assert sleeps == [1.5]
