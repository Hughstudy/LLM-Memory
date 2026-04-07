# LCMemory Build Plan

## Current State

Phase 1 is complete:
- `uv` project initialized with `pyproject.toml`, `uv.lock`
- Dependencies locked: sqlalchemy[asyncio], asyncpg, alembic, pydantic, pydantic-settings, tiktoken
- Dev deps: pytest, pytest-asyncio, ruff, mypy
- `src/lcmemory/` layout scaffolded
- Implemented: `__init__.py`, `config.py`, `logging.py`, `db/base.py`, `db/session.py`, `domain/enums.py`

## Phases

### Phase 2 — Database Models + Alembic [IN PROGRESS]

**Deliverables:**
- `src/lcmemory/db/models.py` — all 7 ORM models
- Alembic init with async env.py
- Initial migration script
- `uv run python -c "from lcmemory.db.models import *"` passes

**Tech verification:**
- SQLAlchemy 2.x mapped_column style (not Column())
- Alembic async template (`alembic init -t async`)
- `async_engine_from_config` + `run_sync` pattern in env.py
- `ConfigDict(from_attributes=True)` for Pydantic ORM compatibility

**Models to implement:**
1. `MemoryCategory` → `memory_categories`
2. `RawMemory` → `raw_memories`
3. `MemorySummary` → `memory_summaries`
4. `SummaryRawMemoryLink` → `summary_raw_memory_links`
5. `SummaryParentLink` → `summary_parent_links`
6. `CompactionJob` → `compaction_jobs`
7. `DelegationGrant` → `delegation_grants`

**Indexes:** category+created_at, compaction_status, summary level

**Verification:** `uv run python -c "from lcmemory.db.models import MemoryCategory, RawMemory, MemorySummary, SummaryRawMemoryLink, SummaryParentLink, CompactionJob, DelegationGrant; print('OK')"`

---

### Phase 3 — Domain Schemas (Pydantic DTOs) + Graph Types

**Deliverables:**
- `src/lcmemory/domain/schemas.py` — all DTOs
- `src/lcmemory/domain/graph_types.py` — graph-specific types

**Tech verification:**
- Pydantic v2 `BaseModel` with `ConfigDict(from_attributes=True)`
- `model_validate()` for ORM → DTO conversion
- `@field_validator` for custom validation
- `@model_validator(mode='after')` for cross-field validation

**DTOs:** CategoryDTO, RawMemoryDTO, SummaryDTO, CompactionJobDTO, DelegationGrantDTO, AddMemoryRequest, MemorySnippet, TruncationInfo, GrepResult, SubtreeNode, DescribeResult, ExpandItem, ExpandResult, ExpandQueryResult, GrepParams, ExpandParams

**Graph types:** SubtreeManifest, GraphPath, DAGEdge

**Verification:** `uv run python -c "from lcmemory.domain.schemas import *; from lcmemory.domain.graph_types import *; print('OK')"`

---

### Phase 4 — Repositories

**Deliverables:**
- `src/lcmemory/db/repositories/categories.py`
- `src/lcmemory/db/repositories/raw_memories.py`
- `src/lcmemory/db/repositories/summaries.py`
- `src/lcmemory/db/repositories/compaction_jobs.py`

**Pattern:** Each repository is a stateless class taking `AsyncSession` per method (not holding sessions). Methods return ORM models or lists. Service layer handles transactions.

**Key methods:**
- CategoryRepo: create, get_by_name, get_by_id, list_all
- RawMemoryRepo: create, get_by_id, list_by_category, count_active_by_category, mark_compacted
- SummaryRepo: create, get_by_id, list_by_category_and_level, count_active_by_category_and_level, mark_superseded
- CompactionJobRepo: create, get_by_id, list_by_status, update_status

**Verification:** `uv run python -c "from lcmemory.db.repositories.categories import CategoryRepository; print('OK')"`

---

### Phase 5 — Ingestion Service

**Deliverables:**
- `src/lcmemory/ingestion/service.py` — `MemoryIngestionService`
- `src/lcmemory/ingestion/validators.py` — input validation

**Key methods:**
- `add_memory(category_name, fact, comment, behavior, metadata) -> RawMemoryDTO`
  - upsert category if not exists
  - create raw memory with combined content_text
  - estimate token count via tiktoken
  - return DTO

**Verification:** `uv run python -c "from lcmemory.ingestion.service import MemoryIngestionService; print('OK')"`

---

### Phase 6 — Compaction Subsystem

**Deliverables:**
- `src/lcmemory/compaction/policy.py` — rules and plan dataclass
- `src/lcmemory/compaction/selector.py` — batch selection
- `src/lcmemory/compaction/prompts.py` — LLM prompt templates
- `src/lcmemory/compaction/llm_client.py` — LLM abstraction (httpx-based)
- `src/lcmemory/compaction/service.py` — `CompactionService`

**Tech verification:**
- `httpx.AsyncClient` for LLM API calls
- `tiktoken` for token counting
- JSON mode / structured output parsing

**Key methods:**
- `compact_raw_batch(category_id) -> SummaryDTO | None`
- `compact_summary_level(category_id, level) -> SummaryDTO | None`
- `run_pending_jobs(limit) -> list[CompactionJobDTO]`

**Verification:** `uv run python -c "from lcmemory.compaction.service import CompactionService; print('OK')"`

---

### Phase 7 — Retrieval Engine

**Deliverables:**
- `src/lcmemory/retrieval/grep.py` — `GrepEngine`
- `src/lcmemory/retrieval/describe.py` — `DescribeEngine`
- `src/lcmemory/retrieval/expand.py` — `ExpandEngine`
- `src/lcmemory/retrieval/query_delegate.py` — `QueryDelegate`

**Tech verification:**
- PostgreSQL `tsvector @@ to_tsquery()` for FTS
- Recursive CTE (`WITH RECURSIVE`) for subtree manifests
- ILIKE fallback for CJK/mixed content

**Key methods:**
- `grep(params: GrepParams) -> GrepResult`
- `describe(summary_id: UUID) -> DescribeResult`
- `expand(params: ExpandParams) -> ExpandResult`
- `expand_query(query, prompt) -> ExpandQueryResult`

**Verification:** `uv run python -c "from lcmemory.retrieval.grep import GrepEngine; print('OK')"`

---

### Phase 8 — Tools API

**Deliverables:**
- `src/lcmemory/tools/contracts.py` — tool definitions (name, description, input schema)
- `src/lcmemory/tools/api.py` — `ToolRegistry` that maps tool names to service methods

**Verification:** `uv run python -c "from lcmemory.tools.api import ToolRegistry; print('OK')"`

---

### Phase 9 — Workers

**Deliverables:**
- `src/lcmemory/workers/scheduler.py` — periodic job scheduler stub
- `src/lcmemory/workers/compaction_worker.py` — background compaction loop

**Verification:** `uv run python -c "from lcmemory.workers.scheduler import CompactionScheduler; print('OK')"`

---

### Phase 10 — Tests

**Deliverables:**
- `tests/fixtures/` — conftest.py with async session fixtures, test database setup
- `tests/unit/` — unit tests for domain logic, policy, selectors
- `tests/integration/` — integration tests for repositories, services, retrieval

**Verification:** `uv run pytest tests/ -v`

---

### Phase 11 — Final Verification

**Checks:**
- `uv run python -c "from lcmemory import *; print('OK')"` passes
- `uv run python -c "from lcmemory.db.models import *; print('OK')"` passes
- `uv run python -c "from lcmemory.domain.schemas import *; print('OK')"` passes
- `uv run python -c "from lcmemory.ingestion.service import MemoryIngestionService; print('OK')"` passes
- `uv run python -c "from lcmemory.compaction.service import CompactionService; print('OK')"` passes
- `uv run python -c "from lcmemory.retrieval.grep import GrepEngine; print('OK')"` passes
- `uv run python -c "from lcmemory.retrieval.describe import DescribeEngine; print('OK')"` passes
- `uv run python -c "from lcmemory.retrieval.expand import ExpandEngine; print('OK')"` passes
- `uv run python -c "from lcmemory.retrieval.query_delegate import QueryDelegate; print('OK')"` passes
- `uv run python -c "from lcmemory.tools.api import ToolRegistry; print('OK')"` passes
- `uv run python -c "from lcmemory.workers.scheduler import CompactionScheduler; print('OK')"` passes
- `uv run ruff check src/` clean
- `uv run pytest tests/` passes (or at least no import errors)
