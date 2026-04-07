from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lcmemory.db.models import MemoryCategory


class CategoryRepository:
    async def create(
        self,
        session: AsyncSession,
        *,
        name: str,
        description: str | None = None,
    ) -> MemoryCategory:
        category = MemoryCategory(name=name, description=description)
        session.add(category)
        await session.flush()
        await session.refresh(category)
        return category

    async def get_by_id(
        self, session: AsyncSession, category_id: uuid.UUID
    ) -> MemoryCategory | None:
        result = await session.execute(
            select(MemoryCategory).where(MemoryCategory.id == category_id)
        )
        return result.scalar_one_or_none()

    async def get_by_name(self, session: AsyncSession, name: str) -> MemoryCategory | None:
        result = await session.execute(select(MemoryCategory).where(MemoryCategory.name == name))
        return result.scalar_one_or_none()

    async def list_all(self, session: AsyncSession) -> list[MemoryCategory]:
        result = await session.execute(select(MemoryCategory))
        return list(result.scalars().all())

    async def get_or_create(
        self,
        session: AsyncSession,
        *,
        name: str,
        description: str | None = None,
    ) -> MemoryCategory:
        category = await self.get_by_name(session, name)
        if category is None:
            category = await self.create(session, name=name, description=description)
        return category
