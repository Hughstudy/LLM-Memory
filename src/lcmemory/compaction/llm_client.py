from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx
from pydantic import BaseModel, ValidationError

from lcmemory.config import Settings


class SummaryPayload(BaseModel):
    title: str
    summary_text: str
    fact_summary: str
    comment_summary: str
    behavior_summary: str


class LLMClient:
    def __init__(self, settings: Settings, *, max_retries: int = 3):
        self.provider = settings.llm_provider
        self.model = settings.llm_model
        self.api_key = settings.llm_api_key
        self.base_url = settings.llm_base_url
        self.temperature = settings.llm_temperature
        self.max_tokens = settings.llm_max_tokens
        self.max_retries = max_retries
        self._client = httpx.AsyncClient(timeout=60.0)

    async def summarize(self, messages: list[dict[str, Any]]) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }

        last_error: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                response = await self._client.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                )
                if response.status_code == httpx.codes.TOO_MANY_REQUESTS:
                    retry_delay = self._get_retry_delay(response, attempt)
                    if attempt == self.max_retries - 1:
                        response.raise_for_status()
                    await asyncio.sleep(retry_delay)
                    continue

                response.raise_for_status()
                data = response.json()
                break
            except (httpx.HTTPError, ValueError) as exc:
                last_error = exc
                if attempt == self.max_retries - 1:
                    raise
                await asyncio.sleep(0.5 * (attempt + 1))
        else:
            if last_error is not None:
                raise last_error
            raise RuntimeError("LLM request failed without an exception")

        content = data["choices"][0]["message"]["content"]
        return self._validate_summary_content(content)

    def _validate_summary_content(self, content: str) -> dict[str, str]:
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            raise ValueError("LLM response was not valid JSON") from exc

        try:
            payload = SummaryPayload.model_validate(parsed)
        except ValidationError as exc:
            raise ValueError("LLM response did not match the required summary schema") from exc

        normalized = {
            "title": payload.title.strip(),
            "summary_text": payload.summary_text.strip(),
            "fact_summary": payload.fact_summary.strip(),
            "comment_summary": payload.comment_summary.strip(),
            "behavior_summary": payload.behavior_summary.strip(),
        }
        missing_fields = [key for key, value in normalized.items() if not value]
        if missing_fields:
            missing = ", ".join(missing_fields)
            raise ValueError(f"LLM response contained empty required fields: {missing}")

        return normalized

    def _get_retry_delay(self, response: httpx.Response, attempt: int) -> float:
        retry_after = response.headers.get("Retry-After")
        if retry_after is not None:
            try:
                return max(float(retry_after), 0.0)
            except ValueError:
                pass
        return max(1.0, 2.0**attempt)

    def count_tokens(self, text: str) -> int:
        try:
            import tiktoken

            try:
                encoding = tiktoken.encoding_for_model(self.model)
            except KeyError:
                encoding = tiktoken.get_encoding("cl100k_base")

            return len(encoding.encode(text))
        except Exception:
            return len(text) // 4
