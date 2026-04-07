from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from lcmemory.compaction.llm_client import LLMClient
from lcmemory.compaction.policy import CompactionPolicy, should_compact
from lcmemory.compaction.prompts import (
    build_raw_compaction_messages,
    build_summary_compaction_messages,
)
from lcmemory.compaction.selector import CompactionSelector
from lcmemory.config import Settings, get_settings
from lcmemory.db.repositories.categories import CategoryRepository
from lcmemory.db.repositories.compaction_jobs import CompactionJobRepository
from lcmemory.db.repositories.raw_memories import RawMemoryRepository
from lcmemory.db.repositories.summaries import SummaryRepository
from lcmemory.domain.enums import CompactionSourceType, JobStatus, SummaryKind
from lcmemory.domain.schemas import CompactionJobDTO, SummaryDTO


class CompactionService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        settings: Settings | None = None,
    ):
        self.session_factory = session_factory
        self.settings = settings or get_settings()
        self.policy = CompactionPolicy(
            threshold=self.settings.compaction_threshold,
            trigger_mode=self.settings.compaction_trigger_mode,
        )
        self.selector = CompactionSelector()
        self.category_repo = CategoryRepository()
        self.llm_client = LLMClient(self.settings, max_retries=self.policy.max_retries)
        self.raw_memory_repo = RawMemoryRepository()
        self.summary_repo = SummaryRepository()
        self.job_repo = CompactionJobRepository()

    async def compact_raw_batch(self, category_id: uuid.UUID) -> SummaryDTO | None:
        batch_id = uuid.uuid4()

        async with self.session_factory() as session:
            active_count = await self.raw_memory_repo.count_active_by_category(session, category_id)
            if not should_compact(active_count, self.policy):
                return None

            batch = await self.selector.select_raw_batch(
                session, category_id, limit=self.policy.threshold
            )
            if len(batch) < self.policy.threshold:
                return None

            raw_memory_ids = [memory.id for memory in batch]
            memories_data = [
                {
                    "id": str(memory.id),
                    "fact": memory.fact,
                    "comment": memory.comment,
                    "behavior": memory.behavior,
                    "created_at": memory.created_at.isoformat() if memory.created_at else None,
                }
                for memory in batch
            ]
            await self.raw_memory_repo.mark_batched(session, raw_memory_ids, batch_id)
            await session.commit()

        try:
            summary_result = await self.llm_client.summarize(
                build_raw_compaction_messages(memories_data)
            )
        except Exception:
            async with self.session_factory() as session:
                await self.raw_memory_repo.mark_active(session, raw_memory_ids)
                await session.commit()
            raise

        token_count = self.llm_client.count_tokens(self._join_summary_parts(summary_result))

        async with self.session_factory() as session:
            summary = await self.summary_repo.create(
                session,
                category_id=category_id,
                level=0,
                kind=SummaryKind.LEAF,
                title=summary_result["title"],
                summary_text=summary_result["summary_text"],
                fact_summary=summary_result["fact_summary"],
                comment_summary=summary_result["comment_summary"],
                behavior_summary=summary_result["behavior_summary"],
                token_count=token_count,
                source_count=len(raw_memory_ids),
                descendant_raw_count=len(raw_memory_ids),
            )
            await self.summary_repo.add_raw_memory_links(session, summary.id, raw_memory_ids)
            await self.raw_memory_repo.mark_compacted(session, raw_memory_ids, batch_id)
            await self._queue_followup_jobs(session, category_id)
            await session.commit()
            return SummaryDTO.model_validate(summary)

    async def compact_summary_level(self, category_id: uuid.UUID, level: int) -> SummaryDTO | None:
        batch_id = uuid.uuid4()

        async with self.session_factory() as session:
            active_count = await self.summary_repo.count_active_by_category_and_level(
                session, category_id, level
            )
            if not should_compact(active_count, self.policy):
                return None

            batch = await self.selector.select_summary_batch(
                session, category_id, level, limit=self.policy.threshold
            )
            if len(batch) < self.policy.threshold:
                return None

            parent_summary_ids = [summary.id for summary in batch]
            summaries_data = [
                {
                    "id": str(summary.id),
                    "title": summary.title,
                    "summary_text": summary.summary_text,
                    "fact_summary": summary.fact_summary,
                    "comment_summary": summary.comment_summary,
                    "behavior_summary": summary.behavior_summary,
                    "created_at": summary.created_at.isoformat() if summary.created_at else None,
                }
                for summary in batch
            ]
            total_descendant_count = sum(summary.descendant_raw_count for summary in batch)
            await self.summary_repo.mark_batched(session, parent_summary_ids, batch_id)
            await session.commit()

        try:
            summary_result = await self.llm_client.summarize(
                build_summary_compaction_messages(summaries_data)
            )
        except Exception:
            async with self.session_factory() as session:
                await self.summary_repo.mark_active(session, parent_summary_ids)
                await session.commit()
            raise

        token_count = self.llm_client.count_tokens(self._join_summary_parts(summary_result))

        async with self.session_factory() as session:
            summary = await self.summary_repo.create(
                session,
                category_id=category_id,
                level=level + 1,
                kind=SummaryKind.CONDENSED,
                title=summary_result["title"],
                summary_text=summary_result["summary_text"],
                fact_summary=summary_result["fact_summary"],
                comment_summary=summary_result["comment_summary"],
                behavior_summary=summary_result["behavior_summary"],
                token_count=token_count,
                source_count=len(parent_summary_ids),
                descendant_raw_count=total_descendant_count,
            )
            await self.summary_repo.add_parent_links(session, summary.id, parent_summary_ids)
            await self.summary_repo.mark_superseded_with_batch(
                session, parent_summary_ids, batch_id
            )
            await self._queue_followup_jobs(session, category_id)
            await session.commit()
            return SummaryDTO.model_validate(summary)

    async def scan_and_queue_jobs(self, limit: int | None = None) -> list[CompactionJobDTO]:
        queued_jobs: list[CompactionJobDTO] = []

        async with self.session_factory() as session:
            categories = await self.category_repo.list_all(session)
            for category in categories:
                if limit is not None and len(queued_jobs) >= limit:
                    break

                raw_count = await self.raw_memory_repo.count_active_by_category(
                    session, category.id
                )
                if should_compact(raw_count, self.policy) and not await self.job_repo.has_open_job(
                    session, category.id, CompactionSourceType.RAW
                ):
                    raw_job = await self.job_repo.create(
                        session,
                        category_id=category.id,
                        source_type=CompactionSourceType.RAW,
                        input_count=min(raw_count, self.policy.threshold),
                        llm_model=self.settings.llm_model,
                        prompt_version="v1",
                    )
                    queued_jobs.append(CompactionJobDTO.model_validate(raw_job))

                eligible_levels = await self.summary_repo.find_eligible_levels(
                    session, category.id, self.policy.threshold
                )
                if eligible_levels and not await self.job_repo.has_open_job(
                    session, category.id, CompactionSourceType.SUMMARY
                ):
                    summary_job = await self.job_repo.create(
                        session,
                        category_id=category.id,
                        source_type=CompactionSourceType.SUMMARY,
                        input_count=self.policy.threshold,
                        llm_model=self.settings.llm_model,
                        prompt_version="v1",
                    )
                    queued_jobs.append(CompactionJobDTO.model_validate(summary_job))

            await session.commit()

        return queued_jobs

    async def run_pending_jobs(self, limit: int = 10) -> list[CompactionJobDTO]:
        processed_jobs: list[CompactionJobDTO] = []

        async with self.session_factory() as session:
            pending_jobs = await self.job_repo.list_by_status(
                session, JobStatus.QUEUED, limit=limit
            )

        for job in pending_jobs:
            async with self.session_factory() as session:
                await self.job_repo.mark_running(session, job.id)
                await session.commit()

            try:
                if job.source_type == CompactionSourceType.RAW:
                    result = await self.compact_raw_batch(job.category_id)
                else:
                    level = await self._find_next_summary_level(job.category_id)
                    result = (
                        await self.compact_summary_level(job.category_id, level)
                        if level is not None
                        else None
                    )

                async with self.session_factory() as session:
                    if result is None:
                        await self.job_repo.mark_failed(session, job.id, "No items to compact")
                    else:
                        await self.job_repo.mark_succeeded(session, job.id, output_count=1)
                    stored_job = await self.job_repo.get_by_id(session, job.id)
                    await session.commit()

                if stored_job is not None:
                    processed_jobs.append(CompactionJobDTO.model_validate(stored_job))
            except Exception as exc:
                async with self.session_factory() as session:
                    await self.job_repo.mark_failed(session, job.id, str(exc))
                    stored_job = await self.job_repo.get_by_id(session, job.id)
                    await session.commit()
                if stored_job is not None:
                    processed_jobs.append(CompactionJobDTO.model_validate(stored_job))

        return processed_jobs

    async def _find_next_summary_level(self, category_id: uuid.UUID) -> int | None:
        async with self.session_factory() as session:
            eligible_levels = await self.summary_repo.find_eligible_levels(
                session, category_id, self.policy.threshold
            )
        return eligible_levels[0] if eligible_levels else None

    async def _queue_followup_jobs(self, session: AsyncSession, category_id: uuid.UUID) -> None:
        raw_count = await self.raw_memory_repo.count_active_by_category(session, category_id)
        if should_compact(raw_count, self.policy) and not await self.job_repo.has_open_job(
            session, category_id, CompactionSourceType.RAW
        ):
            await self.job_repo.create(
                session,
                category_id=category_id,
                source_type=CompactionSourceType.RAW,
                input_count=min(raw_count, self.policy.threshold),
                llm_model=self.settings.llm_model,
                prompt_version="v1",
            )

        eligible_levels = await self.summary_repo.find_eligible_levels(
            session, category_id, self.policy.threshold
        )
        if eligible_levels and not await self.job_repo.has_open_job(
            session, category_id, CompactionSourceType.SUMMARY
        ):
            await self.job_repo.create(
                session,
                category_id=category_id,
                source_type=CompactionSourceType.SUMMARY,
                input_count=self.policy.threshold,
                llm_model=self.settings.llm_model,
                prompt_version="v1",
            )

    def _join_summary_parts(self, summary_result: dict[str, str]) -> str:
        return " ".join(
            part
            for part in (
                summary_result["summary_text"],
                summary_result["fact_summary"],
                summary_result["comment_summary"],
                summary_result["behavior_summary"],
            )
            if part
        )
