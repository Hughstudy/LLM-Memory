from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx

from lcmemory.config import Settings


class LLMClient:
    def __init__(self, settings: Settings):
        self.provider = settings.llm_provider
        self.model = settings.llm_model
        self.api_key = settings.llm_api_key
        self.base_url = settings.llm_base_url
        self.temperature = settings.llm_temperature
        self.max_tokens = settings.llm_max_tokens

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
        for attempt in range(3):
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        f"{self.base_url}/chat/completions",
                        headers=headers,
                        json=payload,
                        timeout=60.0,
                    )
                    response.raise_for_status()
                    data = response.json()
                break
            except (httpx.HTTPError, ValueError) as exc:
                last_error = exc
                if attempt == 2:
                    raise
                await asyncio.sleep(0.5 * (attempt + 1))
        else:
            if last_error is not None:
                raise last_error
            raise RuntimeError("LLM request failed without an exception")

        content = data["choices"][0]["message"]["content"]

        try:
            parsed = json.loads(content)
            return {
                "title": parsed.get("title", ""),
                "summary_text": parsed.get("summary_text", ""),
                "fact_summary": parsed.get("fact_summary", ""),
                "comment_summary": parsed.get("comment_summary", ""),
                "behavior_summary": parsed.get("behavior_summary", ""),
            }
        except (json.JSONDecodeError, KeyError):
            return {
                "title": "",
                "summary_text": content,
                "fact_summary": "",
                "comment_summary": "",
                "behavior_summary": "",
            }

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
