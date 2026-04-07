"""Enumeration types for the memory system."""

from __future__ import annotations

import enum


class CompactionStatus(enum.StrEnum):
    """Lifecycle status of a raw memory or summary node."""

    ACTIVE = "active"
    BATCHED = "batched"
    COMPACTED = "compacted"
    SUPERSEDED = "superseded"


class SummaryKind(enum.StrEnum):
    """Type of summary node in the DAG."""

    LEAF = "leaf"  # level-0: summarises raw memories
    CONDENSED = "condensed"  # level-1+: summarises lower summaries
    ROOT_CANDIDATE = "root_candidate"  # top-level converged summary


class JobStatus(enum.StrEnum):
    """Lifecycle status of a compaction job."""

    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class CompactionSourceType(enum.StrEnum):
    """Source type for a compaction job."""

    RAW = "raw"
    SUMMARY = "summary"


class SearchScope(enum.StrEnum):
    """Scope for memory search operations."""

    MESSAGES = "messages"
    SUMMARIES = "summaries"
    BOTH = "both"


class SearchMode(enum.StrEnum):
    """Search strategy mode."""

    FULL_TEXT = "full_text"
    ILIKE = "ilike"


class NodeType(enum.StrEnum):
    RAW_MEMORY = "raw_memory"
    SUMMARY = "summary"
