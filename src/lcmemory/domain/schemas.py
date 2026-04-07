from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from lcmemory.domain.enums import (
    CompactionSourceType,
    CompactionStatus,
    JobStatus,
    SummaryKind,
)


class CategoryDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID | str
    name: str
    description: str | None = None
    created_at: datetime | None = None


class RawMemoryDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID | str
    category_id: uuid.UUID | str
    category_name: str | None = None
    fact: str
    comment: str
    behavior: str
    token_count: int = 0
    created_at: datetime | None = None
    compaction_status: CompactionStatus
    metadata_json: dict[str, Any] | None = None


class SummaryDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID | str
    category_id: uuid.UUID | str
    category_name: str | None = None
    level: int
    kind: SummaryKind
    title: str | None = None
    summary_text: str = ""
    fact_summary: str = ""
    comment_summary: str = ""
    behavior_summary: str = ""
    token_count: int = 0
    source_count: int = 0
    descendant_raw_count: int = 0
    created_at: datetime | None = None
    compaction_status: CompactionStatus
    metadata_json: dict[str, Any] | None = None


class CompactionJobDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID | str
    category_id: uuid.UUID | str
    source_type: CompactionSourceType
    status: JobStatus
    input_count: int = 0
    output_count: int = 0
    llm_model: str = ""
    prompt_version: str = ""
    error_text: str | None = None
    created_at: datetime | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None


class DelegationGrantDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID | str
    conversation_scope: dict[str, Any]
    token_cap: int
    expires_at: datetime
    revoked_at: datetime | None = None
    created_at: datetime | None = None


class AddMemoryRequest(BaseModel):
    category_name: str = Field(min_length=1)
    fact: str = Field(min_length=1)
    comment: str = Field(min_length=1)
    behavior: str = Field(min_length=1)
    metadata: dict[str, Any] | None = None


class MemorySnippet(BaseModel):
    id: str
    node_type: str
    category: str | None = None
    level: int | None = None
    created_at: datetime | None = None
    snippet: str


class TruncationInfo(BaseModel):
    truncated: bool
    token_cap: int
    used_tokens: int


class GrepResult(BaseModel):
    items: list[MemorySnippet]
    total: int


class SubtreeNode(BaseModel):
    id: str
    depth_from_root: int
    path: str
    child_count: int
    descendant_raw_count: int
    token_count: int


class DescribeResult(BaseModel):
    summary: SummaryDTO
    parents: list[str]
    children: list[str]
    source_raw_memory_ids: list[str]
    subtree: list[SubtreeNode]


class ExpandItem(BaseModel):
    id: str
    node_type: str
    depth: int
    content: str
    fact: str | None = None
    comment: str | None = None
    behavior: str | None = None


class ExpandResult(BaseModel):
    items: list[ExpandItem]
    truncated: bool = False
    used_tokens: int = 0


class ExpandQueryResult(BaseModel):
    answer: str
    cited_ids: list[str]
    expanded_summary_count: int
    total_source_tokens: int
    truncated: bool = False


class GrepParams(BaseModel):
    pattern: str
    mode: str = "full_text"
    scope: str = "both"
    category: str | None = None
    limit: int = 20


class ExpandParams(BaseModel):
    summary_ids: list[str]
    max_depth: int = 3
    include_messages: bool = True
    token_cap: int = 12000
