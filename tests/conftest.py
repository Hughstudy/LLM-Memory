from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncGenerator

import pytest
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from lcmemory.db.base import Base


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def engine_url():
    return "postgresql+asyncpg://postgres:postgres@localhost:5432/lcmemory_test"


@pytest.fixture(scope="session")
async def engine(engine_url):
    eng = create_async_engine(engine_url, echo=False, pool_pre_ping=True)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await eng.dispose()


@pytest.fixture
async def session_factory(engine) -> AsyncGenerator[async_sessionmaker[AsyncSession], None]:
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    yield factory


@pytest.fixture
async def db_session(engine) -> AsyncGenerator[AsyncSession, None]:
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as session:
        yield session


@pytest.fixture
def sample_category_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def sample_raw_memory_data(sample_category_id) -> dict:
    return {
        "category_id": sample_category_id,
        "fact": "Use rotating refresh tokens",
        "comment": "Prevents replay abuse on token refresh",
        "behavior": "Rotate token pair on every refresh call",
        "content_text": (
            "Use rotating refresh tokens "
            "Prevents replay abuse on token refresh "
            "Rotate token pair on every refresh call"
        ),
        "token_count": 18,
        "metadata_json": {"source": "code_review"},
    }
