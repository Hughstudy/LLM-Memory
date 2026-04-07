from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from lcmemory.domain.enums import (
    CompactionSourceType,
    CompactionStatus,
    JobStatus,
    NodeType,
    SearchMode,
    SearchScope,
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
    token_count: int = Field(default=0, ge=0)
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
    token_count: int = Field(default=0, ge=0)
    source_count: int = Field(default=0, ge=0)
    descendant_raw_count: int = Field(default=0, ge=0)
    created_at: datetime | None = None
    compaction_status: CompactionStatus
    metadata_json: dict[str, Any] | None = None


class CompactionJobDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID | str
    category_id: uuid.UUID | str
    source_type: CompactionSourceType
    status: JobStatus
    input_count: int = Field(default=0, ge=0)
    output_count: int = Field(default=0, ge=0)
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
    token_cap: int = Field(ge=0)
    expires_at: datetime
    revoked_at: datetime | None = None
    created_at: datetime | None = None


NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class AddMemoryRequest(BaseModel):
    category_name: NonEmptyStr
    fact: NonEmptyStr
    comment: NonEmptyStr
    behavior: NonEmptyStr
    metadata: dict[str, Any] | None = None


class MemorySnippet(BaseModel):
    id: str
    node_type: NodeType
    category: str | None = None
    level: int | None = None
    created_at: datetime | None = None
    snippet: str


class TruncationInfo(BaseModel):
    truncated: bool
    token_cap: int = Field(ge=0)
    used_tokens: int = Field(ge=0)


class GrepResult(BaseModel):
    items: list[MemorySnippet]
    total: int = Field(ge=0)


class SubtreeNode(BaseModel):
    id: str
    depth_from_root: int = Field(ge=0)
    path: str
    child_count: int = Field(ge=0)
    descendant_raw_count: int = Field(ge=0)
    token_count: int = Field(ge=0)


class DescribeResult(BaseModel):
    summary: SummaryDTO
    parents: list[str]
    children: list[str]
    source_raw_memory_ids: list[str]
    subtree: list[SubtreeNode]


class ExpandItem(BaseModel):
    id: str
    node_type: NodeType
    depth: int = Field(ge=0)
    content: str
    fact: str | None = None
    comment: str | None = None
    behavior: str | None = None


class ExpandResult(BaseModel):
    items: list[ExpandItem]
    truncated: bool = False
    used_tokens: int = Field(default=0, ge=0)


class ExpandQueryResult(BaseModel):
    answer: str
    cited_ids: list[str]
    expanded_summary_count: int = Field(ge=0)
    total_source_tokens: int = Field(ge=0)
    truncated: bool = False


class GrepParams(BaseModel):
    pattern: str
    mode: SearchMode = SearchMode.FULL_TEXT
    scope: SearchScope = SearchScope.BOTH
    category: str | None = None
    limit: int = Field(default=20, gt=0)


class ExpandParams(BaseModel):
    summary_ids: list[str]
    max_depth: int = Field(default=3, ge=0)
    include_messages: bool = True
    token_cap: int = Field(default=12000, gt=0)
