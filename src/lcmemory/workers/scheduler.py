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
    ):
        self._compaction_service = compaction_service
        self._interval_seconds = interval_seconds
        self._running = False

    async def run_once(self) -> int:
        await self._compaction_service.scan_and_queue_jobs()
        jobs = await self._compaction_service.run_pending_jobs()
        return len(jobs)

    async def start(self) -> None:
        self._running = True
        while self._running:
            try:
                count = await self.run_once()
                logger.info(f"Compaction cycle completed, processed {count} jobs")
            except Exception as e:
                logger.error(f"Error in compaction cycle: {e}")
            await asyncio.sleep(self._interval_seconds)

    def stop(self) -> None:
        self._running = False
