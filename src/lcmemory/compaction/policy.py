from __future__ import annotations

import uuid
from dataclasses import dataclass

from lcmemory.domain.enums import CompactionSourceType


@dataclass
class CompactionPolicy:
    threshold: int = 15
    trigger_mode: str = "oldest_first"
    max_retries: int = 3


def should_compact(active_count: int, policy: CompactionPolicy) -> bool:
    return active_count >= policy.threshold


@dataclass
class CompactionPlan:
    category_id: uuid.UUID
    source_type: CompactionSourceType
    batch_size: int
    level: int = 0
