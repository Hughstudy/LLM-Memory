from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from lcmemory.db.models import CompactionJob
from lcmemory.domain.enums import CompactionSourceType, JobStatus


class CompactionJobRepository:
    async def create(
        self,
        session: AsyncSession,
        *,
        category_id: uuid.UUID,
        source_type: CompactionSourceType,
        input_count: int,
        llm_model: str,
        prompt_version: str,
    ) -> CompactionJob:
        job = CompactionJob(
            category_id=category_id,
            source_type=source_type,
            input_count=input_count,
            llm_model=llm_model,
            prompt_version=prompt_version,
        )
        session.add(job)
        await session.flush()
        await session.refresh(job)
        return job

    async def get_by_id(self, session: AsyncSession, job_id: uuid.UUID) -> CompactionJob | None:
        result = await session.execute(select(CompactionJob).where(CompactionJob.id == job_id))
        return result.scalar_one_or_none()

    async def list_by_status(
        self, session: AsyncSession, status: JobStatus, *, limit: int = 10
    ) -> list[CompactionJob]:
        result = await session.execute(
            select(CompactionJob)
            .where(CompactionJob.status == status)
            .order_by(CompactionJob.created_at.asc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def update_status(
        self,
        session: AsyncSession,
        job_id: uuid.UUID,
        *,
        status: JobStatus,
        output_count: int | None = None,
        error_text: str | None = None,
    ) -> None:
        values: dict[str, JobStatus | int | str | datetime] = {"status": status}
        if output_count is not None:
            values["output_count"] = output_count
        if error_text is not None:
            values["error_text"] = error_text
        await session.execute(
            update(CompactionJob).where(CompactionJob.id == job_id).values(**values)
        )

    async def mark_running(self, session: AsyncSession, job_id: uuid.UUID) -> None:
        await session.execute(
            update(CompactionJob)
            .where(CompactionJob.id == job_id)
            .values(status=JobStatus.RUNNING, started_at=datetime.now(UTC))
        )

    async def mark_succeeded(
        self, session: AsyncSession, job_id: uuid.UUID, output_count: int
    ) -> None:
        await session.execute(
            update(CompactionJob)
            .where(CompactionJob.id == job_id)
            .values(
                status=JobStatus.SUCCEEDED,
                output_count=output_count,
                finished_at=datetime.now(UTC),
            )
        )

    async def mark_failed(self, session: AsyncSession, job_id: uuid.UUID, error_text: str) -> None:
        await session.execute(
            update(CompactionJob)
            .where(CompactionJob.id == job_id)
            .values(
                status=JobStatus.FAILED,
                error_text=error_text,
                finished_at=datetime.now(UTC),
            )
        )

    async def has_open_job(
        self,
        session: AsyncSession,
        category_id: uuid.UUID,
        source_type: CompactionSourceType,
    ) -> bool:
        result = await session.execute(
            select(CompactionJob.id)
            .where(
                CompactionJob.category_id == category_id,
                CompactionJob.source_type == source_type,
                CompactionJob.status.in_([JobStatus.QUEUED, JobStatus.RUNNING]),
            )
            .limit(1)
        )
        return result.scalar_one_or_none() is not None
