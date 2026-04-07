# PROJECT KNOWLEDGE BASE

**Generated:** 2026-04-07
**Stack:** Python 3.12 / SQLAlchemy 2.x (async) / PostgreSQL (asyncpg) / Pydantic v2 / Alembic

## OVERVIEW
LLM memory system with hierarchical summary DAG — short-term raw memories are compacted into long-term summaries via LLM, forming a traversable DAG preserved for expandable recall.

## STRUCTURE
```
.
├── src/lcmemory/          # Main package (src layout, uv managed)
│   ├── db/                # SQLAlchemy models, session, repositories
│   │   └── repositories/  # Stateless CRUD classes (session-per-method)
│   ├── domain/            # Enums, Pydantic DTOs, graph types
│   ├── ingestion/         # Write path: add_memory + validators
│   ├── compaction/        # LLM summarization pipeline
│   ├── retrieval/         # Read path: grep/describe/expand/query
│   ├── tools/             # Tool calling API surface (lcm_grep etc.)
│   └── workers/           # Background compaction scheduler
├── migrations/alembic/    # Alembic async migrations
└── tests/                 # pytest-asyncio, conftest in tests/
```

## WHERE TO LOOK
| Task | Location | Notes |
|------|----------|-------|
| Add a DB table | `src/lcmemory/db/models.py` | 7 tables, SQLAlchemy 2.x mapped_column style |
| Add a DTO | `src/lcmemory/domain/schemas.py` | Pydantic v2, ConfigDict(from_attributes=True) |
| Add an enum | `src/lcmemory/domain/enums.py` | Use enum.StrEnum (Python 3.12) |
| Add a repository method | `src/lcmemory/db/repositories/` | Stateless, AsyncSession param per method |
| Add a retrieval tool | `src/lcmemory/retrieval/` + `src/lcmemory/tools/contracts.py` | Register in TOOL_DEFINITIONS list |
| Change compaction rules | `src/lcmemory/compaction/policy.py` | Threshold=15, oldest-first trigger |
| Change LLM prompts | `src/lcmemory/compaction/prompts.py` | System + user message builders |
| Change DB connection | `LCM_DATABASE_URL` env var | Falls back to alembic.ini |
| Change compaction threshold | `LCM_COMPACTION_THRESHOLD` env var | Default 15 |

## CODE MAP
| Symbol | Type | Location | Role |
|--------|------|----------|------|
| MemoryCategory | ORM | db/models.py | Category partition (UUID PK) |
| RawMemory | ORM | db/models.py | Short-term leaf memory (fact/comment/behavior) |
| MemorySummary | ORM | db/models.py | Long-term summary node (level, DAG edges) |
| SummaryRawMemoryLink | ORM | db/models.py | Leaf→raw provenance |
| SummaryParentLink | ORM | db/models.py | Condensed→source provenance |
| CompactionJob | ORM | db/models.py | Job tracking (queued→running→succeeded/failed) |
| DelegationGrant | ORM | db/models.py | Scoped grants for expand_query sub-agents |
| CompactionService | Service | compaction/service.py | Orchestrates raw→leaf and summary→condensed flows |
| MemoryIngestionService | Service | ingestion/service.py | Writes raw memories, triggers compaction check |
| GrepEngine | Retrieval | retrieval/grep.py | FTS + ILIKE search across memories/summaries |
| DescribeEngine | Retrieval | retrieval/describe.py | Subtree manifest via recursive CTE |
| ExpandEngine | Retrieval | retrieval/expand.py | DAG traversal with token cap |
| QueryDelegate | Retrieval | retrieval/query_delegate.py | Bounded deep recall (v0: in-process) |
| ToolRegistry | API | tools/api.py | Routes lcm_* tool calls to engines |
| LLMClient | Client | compaction/llm_client.py | OpenAI-compatible chat via httpx |

## CONVENTIONS
- **Line length**: 100 chars (ruff enforced)
- **Type checking**: mypy strict mode
- **Async everywhere**: asyncpg driver, async_sessionmaker, expire_on_commit=False
- **Repositories are stateless**: take AsyncSession per method, never hold sessions
- **No comments/docstrings**: code is self-documenting (enforced by hook)
- **Imports**: ruff auto-sorts (I rule)
- **Python 3.12+**: no version compat code

## ANTI-PATTERNS (THIS PROJECT)
- Never use `as any` or `@ts-ignore` / type: ignore
- Never physically delete compacted raw memories — only update compaction_status
- Never compact across categories
- Never hold sessions in repository constructors
- Never spawn recursive sub-agents (lcm_expand_query must deny itself)

## UNIQUE STYLES
- **Three-channel memory**: every raw memory has fact/comment/behavior fields; summaries preserve all three
- **DAG over tree**: summary_parent_links allow a summary to be reused by multiple higher summaries
- **GC semantics**: compaction marks items compacted/superseded but preserves raw evidence
- **Compaction threshold**: 15 items triggers batch; oldest-first selection
- **Token budgeting**: expand operations track used_tokens and set truncated flag

## COMMANDS
```bash
uv sync                              # Install dependencies
uv run ruff check src/              # Lint
uv run ruff check src/ --fix        # Auto-fix lint
uv run mypy src/                    # Type check
uv run pytest tests/ -v             # Run tests
uv run pytest tests/unit/ -v        # Unit tests only (no DB required)
uv run alembic upgrade head         # Run migrations (from migrations/)
uv run alembic revision --autogenerate -m "desc"  # Generate migration
```

## NOTES
- DB URL is read from `LCM_DATABASE_URL` env var, falls back to `migrations/alembic.ini`
- Settings singleton via `get_settings()` / `reset_settings()` (for testing)
- `_spawn_sub_agent()` in QueryDelegate raises NotImplementedError — v0 uses in-process fallback
- Alembic env.py imports all models for autogenerate support
