from __future__ import annotations

import asyncio

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


class FlakyCompactionService:
    def __init__(self) -> None:
        self.calls = 0

    async def scan_and_queue_jobs(self) -> list[dict[str, str]]:
        return []

    async def run_pending_jobs(self) -> list[dict[str, str]]:
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("boom")
        return []


async def test_scheduler_uses_backoff_after_failure(monkeypatch) -> None:
    service = FlakyCompactionService()
    scheduler = CompactionScheduler(service, interval_seconds=2.0, max_backoff_multiplier=8.0)
    sleeps: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)
        if len(sleeps) == 2:
            scheduler.stop()

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)

    await scheduler.start()

    assert sleeps == [4.0, 2.0]
