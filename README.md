# LCMemory

LLM memory system with hierarchical summary DAG — short-term raw memories are compacted into long-term summaries via LLM, forming a traversable DAG preserved for expandable recall.

## How It Works

### Three-Channel Memory

Every raw memory stores three semantic fields:

- **fact** — what is true or current
- **comment** — why it matters or why it was done
- **behavior** — how to act or the accepted operating procedure

This structure is preserved through all layers of summarization, so summaries retain facts, rationale, and behavioral guidance.

### DAG Over Tree

Raw memories are terminal leaves. LLM compaction builds summary nodes above them:

```
Level-2 Summary (condensed)
├── Level-1 Summary (condensed)
│   ├── Level-0 Summary (leaf)
│   │   ├── Raw Memory 1
│   │   ├── Raw Memory 2
│   │   └── ...
│   └── Level-0 Summary (leaf)
│       └── ...
└── Level-1 Summary (condensed)
    └── ...
```

A DAG (not a strict tree) because a useful summary can be reused by multiple higher-level summaries. Provenance edges are explicit — you can always traverse from any summary back to the original raw evidence.

### Compaction

When a category accumulates **15 uncompacted** items, the system sends them to an LLM consolidation pipeline. The LLM extracts patterns, removes duplication, and produces a compact summary. Raw evidence is never deleted — only marked `compacted` and excluded from the hot working set. Compaction runs per-category only, never across boundaries.

### Retrieval Tools

| Tool | Purpose | Cost |
|------|---------|------|
| `lcm_grep` | Full-text / ILIKE search across raw memories and summaries | Cheap |
| `lcm_describe` | Inspect a node and its DAG neighborhood (parents, children, subtree manifest) | Medium |
| `lcm_expand` | Walk provenance from summaries down to raw evidence with token cap | Higher |
| `lcm_expand_query` | Delegated deep recall — sub-agent uses bounded tools to answer a query | Highest |

The design keeps common retrieval cheap and pushes expensive reconstruction into bounded, scoped workflows.

## Architecture

```text
             +---------------------+
             |  Tool Calling API   |
             | grep/describe/      |
             | expand/query        |
             +----------+----------+
                        |
                        v
             +---------------------+
             | Retrieval Engine    |
             +----+-----------+----+
                  |           |
                  |           v
                  |   +---------------+
                  |   | LLM Gateway   |
                  |   | summarization |
                  |   | query agent   |
                  |   +-------+-------+
                  |           |
                  v           |
       +-----------------------------+
       | Memory Service              |
       | ingest / compact / DAG ops  |
       +------+----------------------+
              |
              v
       +-----------------------------+
       | PostgreSQL via SQLAlchemy   |
       | categories / raw memories   |
       | summaries / edges / jobs    |
       +-----------------------------+
```

## Project Structure

```
.
├── src/lcmemory/
│   ├── config.py              # Settings (env vars, LLM config, thresholds)
│   ├── logging.py             # Structured logging setup
│   ├── db/
│   │   ├── models.py          # 7 SQLAlchemy ORM models
│   │   ├── session.py         # Async engine + session factory
│   │   └── repositories/      # Stateless CRUD (session-per-method)
│   ├── domain/
│   │   ├── enums.py           # StrEnum types (compaction status, summary kind, etc.)
│   │   ├── schemas.py         # Pydantic v2 DTOs
│   │   └── graph_types.py     # DAG path, subtree manifest types
│   ├── ingestion/
│   │   ├── service.py         # Write path: add_memory + category upsert
│   │   └── validators.py      # Input validation
│   ├── compaction/
│   │   ├── policy.py          # Threshold rules (15 items, oldest-first)
│   │   ├── selector.py        # Batch selection logic
│   │   ├── prompts.py         # LLM prompt builders
│   │   ├── llm_client.py      # OpenAI-compatible chat via httpx
│   │   └── service.py         # Orchestrates raw→leaf and summary→condensed flows
│   ├── retrieval/
│   │   ├── grep.py            # FTS + ILIKE search
│   │   ├── describe.py        # Subtree manifest via recursive CTE
│   │   ├── expand.py          # DAG traversal with token cap
│   │   └── query_delegate.py  # Bounded deep recall (v0: in-process)
│   ├── tools/
│   │   ├── contracts.py       # Tool definitions (name, description, input schema)
│   │   └── api.py             # ToolRegistry: routes lcm_* calls to engines
│   └── workers/
│       ├── scheduler.py       # Periodic compaction scheduler
│       └── compaction_worker.py
├── migrations/alembic/        # Async Alembic migrations
├── tests/
│   ├── unit/                  # Domain logic, policy, selectors
│   ├── integration/           # Repository, service, retrieval tests
│   └── fixtures/
└── pyproject.toml
```

## Data Model

7 tables in PostgreSQL:

| Table | Purpose |
|-------|---------|
| `memory_categories` | Top-level partition (UUID PK, unique name) |
| `raw_memories` | Short-term leaf memory (fact/comment/behavior, compaction status) |
| `memory_summaries` | Long-term summary nodes (level, kind, three-channel summaries) |
| `summary_raw_memory_links` | Leaf summary → raw memory provenance |
| `summary_parent_links` | Condensed summary → source summary provenance |
| `compaction_jobs` | Job tracking (queued → running → succeeded/failed) |
| `delegation_grants` | Scoped grants for expand_query sub-agents |

## Setup

### Prerequisites

- Python 3.12+
- PostgreSQL 15+ with asyncpg support
- [uv](https://docs.astral.sh/uv/)

### Install

```bash
git clone git@github.com:Hughstudy/LLM-Memory.git
cd LLM-Memory
uv sync
```

### Configure

Set environment variables:

```bash
export LCM_DATABASE_URL="postgresql+asyncpg://user:pass@localhost:5432/lcmemory"
export LCM_OPENAI_BASE_URL="https://api.openai.com/v1"    # or any OpenAI-compatible endpoint
export LCM_OPENAI_API_KEY="sk-..."
export LCM_OPENAI_MODEL="gpt-4o"                           # model for summarization
# Optional:
export LCM_COMPACTION_THRESHOLD=15                         # default: 15
```

### Run Migrations

```bash
uv run alembic upgrade head
```

Generate a new migration after model changes:

```bash
uv run alembic revision --autogenerate -m "description"
```

## Development

```bash
uv sync                              # Install dependencies
uv run ruff check src/               # Lint
uv run ruff check src/ --fix         # Auto-fix lint
uv run mypy src/                     # Type check (strict mode)
uv run pytest tests/ -v              # Run all tests
uv run pytest tests/unit/ -v         # Unit tests only (no DB required)
```

## Key Design Decisions

- **DAG over tree** — summaries can be reused by multiple higher-level summaries; provenance is explicit, not path-implied
- **GC semantics, not deletion** — compaction marks items compacted/superseded but preserves raw evidence for audit and recovery
- **Per-category isolation** — compaction never crosses category boundaries
- **Three-channel preservation** — summaries carry fact/comment/behavior fields; absent channels are stored as empty rather than dropped
- **Stateless repositories** — take AsyncSession per method, never hold sessions; transaction boundaries owned by service layer
- **Token budgeting** — expand operations track used tokens and set truncated flags to stay within bounds
- **Delegated recall is bounded** — expand_query sub-agents get scoped grants (category/node-limited, token-capped, time-limited) and cannot recursively spawn

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Language | Python 3.12+ |
| Package manager | uv |
| ORM | SQLAlchemy 2.x (async) |
| Database | PostgreSQL (asyncpg) |
| Validation | Pydantic v2 |
| Migrations | Alembic (async) |
| LLM client | httpx (OpenAI-compatible) |
| Tokenization | tiktoken |
| Linting | ruff |
| Type checking | mypy (strict) |
| Testing | pytest + pytest-asyncio |

## License

MIT
