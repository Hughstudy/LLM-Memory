from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lcmemory.compaction.service import CompactionService

logger = logging.getLogger(__name__)


class CompactionScheduler:
    def __init__(
        self,
        compaction_service: CompactionService,
        interval_seconds: float = 60.0,
        max_backoff_multiplier: float = 8.0,
    ):
        self._compaction_service = compaction_service
        self._interval_seconds = interval_seconds
        self._max_backoff_multiplier = max_backoff_multiplier
        self._running = False

    async def run_once(self) -> int:
        await self._compaction_service.scan_and_queue_jobs()
        jobs = await self._compaction_service.run_pending_jobs()
        return len(jobs)

    async def start(self) -> None:
        self._running = True
        consecutive_failures = 0
        while self._running:
            try:
                count = await self.run_once()
                consecutive_failures = 0
                logger.info(f"Compaction cycle completed, processed {count} jobs")
            except Exception as e:
                consecutive_failures += 1
                logger.error(f"Error in compaction cycle: {e}")
            backoff_multiplier = min(2**consecutive_failures, self._max_backoff_multiplier)
            await asyncio.sleep(self._interval_seconds * backoff_multiplier)

    def stop(self) -> None:
        self._running = False
