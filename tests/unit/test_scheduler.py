from __future__ import annotations

from lcmemory.workers.scheduler import CompactionScheduler


class StubCompactionService:
    def __init__(self) -> None:
        self.scanned = False
        self.processed = False

    async def scan_and_queue_jobs(self) -> list[dict[str, str]]:
        self.scanned = True
        return []

    async def run_pending_jobs(self) -> list[dict[str, str]]:
        self.processed = True
        return [{"id": "job-1"}, {"id": "job-2"}]


async def test_scheduler_run_once_scans_and_processes_jobs() -> None:
    service = StubCompactionService()
    scheduler = CompactionScheduler(service, interval_seconds=0.01)

    processed = await scheduler.run_once()

    assert processed == 2
    assert service.scanned is True
    assert service.processed is True
