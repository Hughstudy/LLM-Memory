from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from lcmemory.compaction.policy import CompactionPolicy, should_compact
from lcmemory.config import get_settings
from lcmemory.db.repositories.categories import CategoryRepository
from lcmemory.db.repositories.compaction_jobs import CompactionJobRepository
from lcmemory.db.repositories.raw_memories import RawMemoryRepository
from lcmemory.domain.enums import CompactionSourceType
from lcmemory.domain.schemas import RawMemoryDTO
from lcmemory.ingestion.validators import build_content_text, validate_memory_input


class MemoryIngestionService:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self.session_factory = session_factory
        self.category_repo = CategoryRepository()
        self.job_repo = CompactionJobRepository()
        self.raw_memory_repo = RawMemoryRepository()

    async def add_memory(
        self,
        *,
        category_name: str,
        fact: str,
        comment: str,
        behavior: str,
        metadata: dict[str, Any] | None = None,
    ) -> RawMemoryDTO:
        validate_memory_input(fact, comment, behavior)

        async with self.session_factory() as session:
            category = await self.category_repo.get_or_create(session, name=category_name)

            content_text = build_content_text(fact, comment, behavior)

            settings = get_settings()
            try:
                import tiktoken

                encoding = tiktoken.get_encoding(settings.token_counter_encoding)
                token_count = len(encoding.encode(content_text))
            except Exception:
                token_count = len(content_text) // 4

            raw_memory = await self.raw_memory_repo.create(
                session,
                category_id=category.id,
                fact=fact,
                comment=comment,
                behavior=behavior,
                content_text=content_text,
                token_count=token_count,
                metadata_json=metadata,
            )

            active_count = await self.raw_memory_repo.count_active_by_category(session, category.id)
            policy = CompactionPolicy(threshold=settings.compaction_threshold)
            if should_compact(active_count, policy) and not await self.job_repo.has_open_job(
                session, category.id, CompactionSourceType.RAW
            ):
                await self.job_repo.create(
                    session,
                    category_id=category.id,
                    source_type=CompactionSourceType.RAW,
                    input_count=min(active_count, settings.compaction_threshold),
                    llm_model=settings.llm_model,
                    prompt_version="v1",
                )

            await session.commit()

            return RawMemoryDTO.model_validate(raw_memory)

    async def get_active_count(self, category_name: str) -> int:
        async with self.session_factory() as session:
            category = await self.category_repo.get_by_name(session, category_name)
            if category is None:
                return 0
            return await self.raw_memory_repo.count_active_by_category(session, category.id)
