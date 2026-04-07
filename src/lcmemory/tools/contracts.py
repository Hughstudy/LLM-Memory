from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class ToolDefinition:
    name: str
    description: str
    input_schema: dict[str, Any]


TOOL_DEFINITIONS: list[ToolDefinition] = [
    ToolDefinition(
        name="lcm_grep",
        description="Search across raw memories and summaries using full-text or pattern matching",
        input_schema={
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Search pattern or query string",
                },
                "mode": {
                    "type": "string",
                    "enum": ["full_text", "ilike"],
                    "default": "full_text",
                    "description": "Search mode: full_text for FTS, ilike for pattern matching",
                },
                "scope": {
                    "type": "string",
                    "enum": ["messages", "summaries", "both"],
                    "default": "both",
                    "description": "Scope of search: messages, summaries, or both",
                },
                "category": {
                    "type": "string",
                    "description": "Filter results by category name",
                },
                "limit": {
                    "type": "integer",
                    "default": 20,
                    "description": "Maximum number of results to return",
                },
            },
            "required": ["pattern"],
        },
    ),
    ToolDefinition(
        name="lcm_describe",
        description=(
            "Inspect a summary node and its DAG neighborhood "
            "including parents, children, and subtree manifest"
        ),
        input_schema={
            "type": "object",
            "properties": {
                "id": {
                    "type": "string",
                    "format": "uuid",
                    "description": "UUID of the summary to describe",
                },
            },
            "required": ["id"],
        },
    ),
    ToolDefinition(
        name="lcm_expand",
        description=(
            "Walk the summary DAG upward through derived summaries and optionally "
            "include raw memories for visited leaf summaries"
        ),
        input_schema={
            "type": "object",
            "properties": {
                "summary_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of summary UUIDs to start expansion from",
                },
                "max_depth": {
                    "type": "integer",
                    "default": 3,
                    "description": "Maximum depth to traverse upward through derived summaries",
                },
                "include_messages": {
                    "type": "boolean",
                    "default": True,
                    "description": "Whether to include raw memories for visited leaf summaries",
                },
                "token_cap": {
                    "type": "integer",
                    "default": 12000,
                    "description": "Maximum tokens to include before truncating",
                },
            },
            "required": ["summary_ids"],
        },
    ),
    ToolDefinition(
        name="lcm_expand_query",
        description=(
            "Delegated deep recall: automatically find and expand "
            "relevant memories to answer a query"
        ),
        input_schema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query to find relevant memories",
                },
                "prompt": {
                    "type": "string",
                    "description": "Additional context or instructions for the query",
                },
                "max_expand_tokens": {
                    "type": "integer",
                    "default": 16000,
                    "description": "Maximum tokens for expansion",
                },
                "ttl_seconds": {
                    "type": "integer",
                    "default": 300,
                    "description": "Time-to-live for the delegation grant in seconds",
                },
            },
            "required": ["query", "prompt"],
        },
    ),
]
