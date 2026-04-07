# LLM Memory System Architecture

## 1. Goal

Build a Python-based LLM memory system that uses:

- `uv` to manage the package, lockfile, and developer workflow
- SQLAlchemy 2.x to manage PostgreSQL persistence
- a two-tier memory model:
  - **short-term memory** for raw memory units
  - **long-term memory** for recursively condensed summaries

The design must preserve every original short-term memory item while allowing the agent to move from high-level summaries back down to raw evidence through a DAG-shaped memory graph.

## 2. Core Concepts

### 2.1 Memory categories

Each memory belongs to a logical category identified by:

- `category_id: UUID`
- `category_name: str`

Examples:

- `project_state`
- `auth_strategy`
- `deployment_incidents`

The category is the top-level partition for compaction, retrieval, and traversal.

### 2.2 Short-term memory

Short-term memory stores raw memory entries. Each entry has three semantic fields:

- `fact`: what the current memory is
- `comment`: why this matters / why it was done
- `behavior`: how to do this / accepted operating behavior

This layer is append-heavy and cheap to query. It is the leaf evidence layer.

### 2.3 Long-term memory

When a category accumulates more than **15 raw short-term memory entries** that are not yet compacted, the system sends them to an LLM consolidation pipeline.

The LLM produces one or more long-term summary nodes that:

- extract patterns
- remove duplication
- preserve rationale and operating guidance
- retain provenance to every source node

This acts like GC/compaction, but **not deletion of knowledge**. Raw evidence remains stored and addressable.

### 2.4 DAG model

The full memory structure should be treated as a **memory DAG**:

- **raw short-term memories are the terminal leaves**
- **level-0 summaries** are the first abstraction layer built over raw leaves
- **higher-order summaries** summarize groups of lower summaries
- every summary node can point to multiple parent/source nodes
- traversal must always be able to recover the path back to original raw messages

Why DAG instead of strict tree:

- a useful pattern may belong to more than one higher-level concept
- later consolidation may reuse earlier summaries
- provenance must be explicit rather than implied by path only

Recommended invariant:

- source edges always point from a more abstract summary to its source summaries or source raw memories
- cycles are forbidden
- each compaction batch belongs to one category only

### 2.5 Reference alignment

This design intentionally combines two nearby implementation patterns:

- the **LCM-style hierarchical recall flow** from the adjacent `lossless-claw-enhanced` project (`lcm_grep`, `lcm_describe`, `lcm_expand`, `lcm_expand_query` semantics)
- the **memory-service packaging mindset** from the adjacent `memory-lancedb-pro` project

The difference is deliberate: this project ports those ideas to **Python + uv + SQLAlchemy + PostgreSQL**, instead of TypeScript + SQLite/LanceDB.

## 3. High-Level Architecture

```text
                +---------------------+
                |  Tool Calling API   |
                | grep/describe/...   |
                +----------+----------+
                           |
                           v
                +---------------------+
                | Retrieval Engine    |
                | grep/describe/      |
                | expand/query        |
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

## 4. Suggested Python Package Layout

Use a modern `src/` layout managed by `uv`.

```text
.
├── pyproject.toml
├── uv.lock
├── README.md
├── ARCHITECTURE.md
├── src/
│   └── lcmemory/
│       ├── __init__.py
│       ├── config.py
│       ├── logging.py
│       ├── db/
│       │   ├── __init__.py
│       │   ├── base.py
│       │   ├── models.py
│       │   ├── session.py
│       │   └── repositories/
│       │       ├── categories.py
│       │       ├── raw_memories.py
│       │       ├── summaries.py
│       │       └── compaction_jobs.py
│       ├── domain/
│       │   ├── enums.py
│       │   ├── schemas.py
│       │   └── graph_types.py
│       ├── ingestion/
│       │   ├── service.py
│       │   └── validators.py
│       ├── compaction/
│       │   ├── policy.py
│       │   ├── selector.py
│       │   ├── prompts.py
│       │   ├── llm_client.py
│       │   └── service.py
│       ├── retrieval/
│       │   ├── grep.py
│       │   ├── describe.py
│       │   ├── expand.py
│       │   └── query_delegate.py
│       ├── tools/
│       │   ├── api.py
│       │   └── contracts.py
│       └── workers/
│           ├── scheduler.py
│           └── compaction_worker.py
├── tests/
│   ├── unit/
│   ├── integration/
│   └── fixtures/
└── migrations/
```

## 5. Module Responsibilities

### `config.py`
- loads environment and runtime configuration
- includes database DSN, LLM provider config, compaction thresholds, token budgets, and security TTLs

### `db/`
- defines SQLAlchemy declarative models
- creates async engine and `async_sessionmaker`
- contains repository classes for persistence boundaries

### `ingestion/service.py`
- writes new short-term memory entries
- attaches category metadata
- emits compaction trigger if threshold is crossed

### `compaction/policy.py`
- defines rules like:
  - compact after 15 uncompacted raw items
  - compact after 15 child summaries into a higher summary
  - never compact across categories
  - do not mix partially failed batches

### `compaction/selector.py`
- selects eligible raw memories or summaries for compaction
- ensures deterministic ordering, e.g. oldest-first by category

### `compaction/service.py`
- orchestrates summarization batch lifecycle
- creates summary nodes and graph edges
- marks source nodes as compacted by batch
- preserves lineage and idempotency

### `retrieval/grep.py`
- full text / fallback text search across raw memories and summaries

### `retrieval/describe.py`
- explains one node and its local DAG neighborhood

### `retrieval/expand.py`
- recursively walks summary provenance toward lower-level detail
- enforces token caps and truncation markers

### `retrieval/query_delegate.py`
- performs delegated deep recall using a bounded sub-agent session
- exposes only safe retrieval tools to that sub-agent

### `tools/api.py`
- tool registration layer for MCP or equivalent tool-calling surface
- maps JSON tool inputs to service methods

### `workers/`
- background worker for compaction jobs
- can later support cron, queue, or event-driven execution

## 6. Data Model

Use PostgreSQL as the source of truth. Use SQLAlchemy ORM/Core for access. For search:

- baseline: PostgreSQL full text search via `tsvector`
- CJK/mixed-language fallback: trigram / `ILIKE` / optional PGroonga later

Do **not** copy the SQLite-specific implementation literally. Preserve the same API semantics, but use PostgreSQL-native equivalents.

### 6.1 Tables

#### `memory_categories`

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | stable category ID |
| `name` | text unique | human-meaningful category name |
| `description` | text nullable | optional scope |
| `created_at` | timestamptz | |

#### `raw_memories`

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | raw leaf memory |
| `category_id` | UUID FK | partition key |
| `fact` | text | what is true/current |
| `comment` | text | why it matters |
| `behavior` | text | how to act |
| `content_text` | text | denormalized combined text for search |
| `token_count` | int | source budgeting |
| `created_at` | timestamptz | insertion order |
| `compaction_status` | enum | `active`, `batched`, `compacted` |
| `compaction_batch_id` | UUID nullable | batch lineage |
| `metadata_json` | jsonb | extra tags |

#### `memory_summaries`

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | summary node ID |
| `category_id` | UUID FK | same-category invariant |
| `level` | int | 0 for leaf summaries over raw memories; 1+ for higher-order summaries |
| `kind` | enum | `leaf`, `condensed`, `root_candidate` |
| `title` | text | short label |
| `summary_text` | text | condensed content |
| `fact_summary` | text | extracted facts |
| `comment_summary` | text | extracted rationale |
| `behavior_summary` | text | extracted behavioral guidance |
| `token_count` | int | stored summary size |
| `source_count` | int | number of immediate source nodes |
| `descendant_raw_count` | int | raw evidence count below node |
| `created_at` | timestamptz | |
| `compaction_status` | enum | `active`, `batched`, `superseded` |
| `compaction_batch_id` | UUID nullable | lineage |
| `metadata_json` | jsonb | evals / quality / tags |

#### `summary_raw_memory_links`

Links leaf summaries to original raw memories.

| Column | Type | Notes |
|---|---|---|
| `summary_id` | UUID FK | summary node |
| `raw_memory_id` | UUID FK | source raw memory |
| `position` | int | deterministic ordering |

Composite PK: (`summary_id`, `raw_memory_id`)

#### `summary_parent_links`

Links higher-order summaries to source summary nodes.

| Column | Type | Notes |
|---|---|---|
| `summary_id` | UUID FK | child / more abstract node |
| `parent_summary_id` | UUID FK | source summary node it was built from |
| `position` | int | deterministic ordering |

Composite PK: (`summary_id`, `parent_summary_id`)

Note: naming follows your requested semantics even though `parent_summary_id` is really a provenance/source edge. If implementation clarity matters more, rename to `source_summary_id`.

#### `compaction_jobs`

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | job ID |
| `category_id` | UUID FK | batch scope |
| `source_type` | enum | `raw` or `summary` |
| `status` | enum | `queued`, `running`, `succeeded`, `failed` |
| `input_count` | int | batch size |
| `output_count` | int | number of summary nodes created |
| `llm_model` | text | auditability |
| `prompt_version` | text | reproducibility |
| `error_text` | text nullable | failure reason |
| `created_at` | timestamptz | |
| `started_at` | timestamptz nullable | |
| `finished_at` | timestamptz nullable | |

#### `delegation_grants`

Tracks scoped grants for `lcm_expand_query` sub-agents.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | grant token ID |
| `conversation_scope` | jsonb | allowed category or node IDs |
| `token_cap` | int | expansion budget |
| `expires_at` | timestamptz | TTL |
| `revoked_at` | timestamptz nullable | cleanup |

## 7. Graph Semantics

### 7.1 Recommended compaction flow

1. Raw memories are appended to `raw_memories`
2. Once there are 15 uncompacted raw memories in one category, create a compaction job
3. LLM creates one leaf summary node from that batch
4. Store provenance in `summary_raw_memory_links`
5. When there are 15 active summaries at the same level in one category, compact them into a higher-level summary node
6. Store provenance in `summary_parent_links`
7. Repeat recursively until no level has 15 eligible siblings

### 7.2 GC behavior

"Clean short term memory" should mean:

- remove raw memories from the hot working set
- mark them `compacted`
- exclude them from default short-term retrieval
- keep them queryable for evidence recovery and auditing

Avoid physical deletion unless you introduce a separate retention policy.

### 7.3 Root behavior

Per category, the graph may have:

- one root candidate when the hierarchy converges
- multiple active top nodes when the knowledge has not fully merged yet

So the structure is a DAG forest per category, not necessarily a single tree at all times.

## 8. SQLAlchemy Design Notes

Recommended baseline:

- Python 3.12+
- SQLAlchemy 2.x async ORM
- `asyncpg` driver
- Alembic for migrations
- `async_sessionmaker(..., expire_on_commit=False)`
- transaction boundaries owned by service layer

Recommended patterns:

- `create_async_engine()` for database engine creation
- one declarative base in `db/base.py`
- repository methods stay narrow; orchestration stays in services
- eager loading for traversal-heavy reads to avoid N+1 issues
- use recursive CTEs for subtree manifests and ancestry expansion

## 9. Retrieval API Specification

## 9.1 Common response types

### `MemorySnippet`

```json
{
  "id": "sum_abc123",
  "nodeType": "summary",
  "category": "auth_strategy",
  "level": 2,
  "createdAt": "2026-03-29T10:00:00Z",
  "snippet": "Discussed JWT token rotation and refresh boundaries..."
}
```

### `TruncationInfo`

```json
{
  "truncated": true,
  "tokenCap": 8000,
  "usedTokens": 7910
}
```

## 9.2 Tool 1: `lcm_grep`

Cheap search across raw and summary memory.

### Signature

```python
lcm_grep(pattern: str, mode: str = "full_text", scope: str = "both") -> GrepResult
```

### Input contract

```json
{
  "pattern": "JWT token",
  "mode": "full_text",
  "scope": "both",
  "category": null,
  "limit": 20
}
```

### Behavior

- `scope=messages` searches `raw_memories`
- `scope=summaries` searches `memory_summaries`
- `scope=both` searches both and merges by relevance/time
- `mode=full_text` uses Postgres FTS where possible
- fallback path uses `ILIKE` or trigram matching

### Output

```json
{
  "items": [
    {
      "id": "sum_abc123",
      "nodeType": "summary",
      "category": "auth_strategy",
      "level": 1,
      "createdAt": "2026-03-29T10:00:00Z",
      "snippet": "Discussed JWT tokens and refresh handling..."
    }
  ],
  "total": 1
}
```

### Python service surface

```python
class RetrievalEngine:
    async def grep(
        self,
        pattern: str,
        *,
        mode: str = "full_text",
        scope: str = "both",
        category: str | None = None,
        limit: int = 20,
    ) -> GrepResult: ...
```

## 9.3 Tool 2: `lcm_describe`

Inspect one summary node and its DAG neighborhood.

### Signature

```python
lcm_describe(id: str) -> DescribeResult
```

### Behavior

Fetch in parallel:

1. summary record
2. immediate parents/source summaries
3. immediate children/derived summaries
4. source raw memory IDs if leaf
5. subtree manifest using recursive CTE

### Output shape

```json
{
  "summary": {
    "id": "sum_abc123",
    "category": "auth_strategy",
    "level": 2,
    "kind": "condensed",
    "title": "JWT strategy evolution",
    "summaryText": "..."
  },
  "parents": ["sum_p1", "sum_p2"],
  "children": ["sum_c1"],
  "sourceRawMemoryIds": [],
  "subtree": [
    {
      "id": "sum_abc123",
      "depthFromRoot": 0,
      "path": "",
      "childCount": 3,
      "descendantRawCount": 45,
      "tokenCount": 230
    }
  ]
}
```

### PostgreSQL note

Your sample recursive CTE is SQLite-oriented. In PostgreSQL, implement the same behavior using `WITH RECURSIVE` plus array/text path accumulation.

## 9.4 Tool 3: `lcm_expand`

Recover progressively more detail from selected summary nodes.

### Signature

```python
lcm_expand(summary_ids: list[str], max_depth: int = 3, include_messages: bool = True, token_cap: int = 12000) -> ExpandResult
```

### Behavior

1. start from requested summary IDs
2. include each summary's content
3. walk to source summaries through `summary_parent_links`
4. when a leaf summary is reached and `include_messages=true`, fetch linked raw memories from `summary_raw_memory_links`
5. stop when `max_depth` or `token_cap` is reached
6. return `truncated=true` when budget cuts off expansion

### Output shape

```json
{
  "items": [
    {
      "id": "sum_def456",
      "nodeType": "summary",
      "depth": 0,
      "content": "..."
    },
    {
      "id": "raw_001",
      "nodeType": "raw_memory",
      "depth": 2,
      "fact": "Use rotating refresh tokens",
      "comment": "Prevents replay abuse",
      "behavior": "Rotate token pair on refresh"
    }
  ],
  "truncated": false,
  "usedTokens": 1180
}
```

## 9.5 Tool 4: `lcm_expand_query`

Delegated deep recall through a bounded sub-agent.

### Signature

```python
lcm_expand_query(
    query: str,
    prompt: str,
    *,
    max_expand_tokens: int = 16000,
    ttl_seconds: int = 300,
) -> ExpandQueryResult
```

### Workflow

1. run `lcm_grep` to find seed summaries/raw memories
2. create scoped delegation grant
3. spawn sub-agent session
4. grant only `lcm_grep`, `lcm_describe`, `lcm_expand`
5. deny recursive `lcm_expand_query`
6. let sub-agent gather evidence and answer prompt
7. return answer with citations and truncation metadata
8. revoke grant and tear down session

### Output shape

```json
{
  "answer": "The decided strategy was to run migrations with explicit revision reviews before deploy.",
  "citedIds": ["sum_123", "raw_98"],
  "expandedSummaryCount": 4,
  "totalSourceTokens": 6200,
  "truncated": false
}
```

## 10. Service-Level Python Interfaces

```python
class MemoryIngestionService:
    async def add_memory(
        self,
        *,
        category_name: str,
        fact: str,
        comment: str,
        behavior: str,
        metadata: dict | None = None,
    ) -> RawMemoryDTO: ...


class CompactionService:
    async def compact_raw_batch(self, category_id: UUID) -> SummaryDTO | None: ...
    async def compact_summary_level(self, category_id: UUID, level: int) -> SummaryDTO | None: ...
    async def run_pending_jobs(self, limit: int = 10) -> list[CompactionJobDTO]: ...


class RetrievalEngine:
    async def grep(self, pattern: str, **kwargs) -> GrepResult: ...
    async def describe(self, id: str) -> DescribeResult: ...
    async def expand(self, summary_ids: list[str], **kwargs) -> ExpandResult: ...
    async def expand_query(self, query: str, prompt: str, **kwargs) -> ExpandQueryResult: ...
```

## 11. Compaction Algorithm

### Raw to leaf summary

Input: 15 oldest active `raw_memories` in one category.

Prompt objective for LLM:

- extract stable facts
- extract rationale
- extract accepted behaviors/process
- remove duplication
- preserve contradictions as explicit notes
- produce compact summary plus optional title/tags

Output:

- 1 level-0 summary node
- provenance edges to all 15 raw memories
- source raw memories marked `compacted`

### Summary to higher summary

Input: 15 active summaries at the same level in one category.

Output:

- 1 condensed summary node at `level + 1`
- provenance edges to source summaries
- source summaries marked `superseded` or `batched`

### Important quality rule

Before finalizing compaction, validate that the output summary contains all three channels when possible:

- facts
- rationale/comments
- behavior/how-to guidance

If one channel is absent, store it as empty string plus metadata rather than silently dropping the field.

## 12. Retrieval Strategy

### Cheap retrieval

Use `lcm_grep` first for candidate discovery.

### Graph-aware inspection

Use `lcm_describe` to inspect a node's neighborhood before paying expansion cost.

### Evidence recovery

Use `lcm_expand` only for high-signal branches.

### Deep delegated recall

Use `lcm_expand_query` when the caller wants an answer rather than raw graph navigation.

This keeps the common path cheap and pushes expensive reconstruction into bounded workflows.

## 13. API and Security Constraints

- all tool calls must be read-only except ingestion/administration tools added later
- `lcm_expand_query` must issue least-privilege grants
- grants must be category/node scoped, token capped, and time-limited
- returned citations must always include stable IDs
- recursive agent spawning must be blocked

## 14. Operational Plan

### Phase 1 - Project foundation

1. initialize package with `uv`
2. create `pyproject.toml` with runtime and dev dependency groups
3. add SQLAlchemy, asyncpg, Alembic, Pydantic, pytest, ruff, mypy
4. create `src/` package and config/session scaffolding

Deliverable: runnable project skeleton with locked dependencies.

### Phase 2 - Database schema

1. implement SQLAlchemy models
2. add Alembic environment and first migration
3. add indexes:
   - category + created_at
   - compaction status
   - summary level
   - FTS/trigram indexes on combined text
4. seed one or two categories in tests

Deliverable: PostgreSQL schema with migration support.

### Phase 3 - Ingestion and compaction core

1. implement `MemoryIngestionService.add_memory()`
2. implement raw-batch selection logic
3. implement LLM summarization adapter
4. write leaf-summary compaction flow
5. write higher-order summary compaction flow
6. add idempotency and retry behavior for failed jobs

Deliverable: end-to-end raw-to-summary compaction.

### Phase 4 - Retrieval engine

1. implement `lcm_grep`
2. implement `lcm_describe`
3. implement `lcm_expand`
4. benchmark traversal and token budgeting
5. add citation-ready DTOs

Deliverable: usable memory navigation API.

### Phase 5 - Delegated recall

1. implement grant model and grant validator
2. integrate sub-agent session creation
3. expose limited retrieval toolset to sub-agent
4. implement `lcm_expand_query`
5. add audit logs and revocation cleanup

Deliverable: bounded deep-recall tool.

### Phase 6 - Quality and operations

1. add unit tests for graph invariants
2. add integration tests for recursive expansion
3. add evaluation set for summary quality
4. add observability for compaction rate, token usage, retrieval latency
5. add retention and archival policy if needed

Deliverable: production-hardening layer.

## 15. Testing Plan

### Unit tests

- repository CRUD
- compaction eligibility rules
- graph cycle prevention
- token cap truncation
- retrieval result ordering

### Integration tests

- insert 16 raw memories -> 1 compaction job -> 1 leaf summary
- insert 15 leaf summaries -> 1 higher-order summary
- expand from top node back to raw evidence
- describe returns correct subtree manifest
- grant expires / revokes correctly

### Property-style invariants

- no cross-category edges
- every summary has provenance
- every raw memory remains reachable from at least one summary after compaction
- graph traversal never loops

## 16. Open Design Decisions

These should be resolved during implementation kickoff:

1. **Exactly one summary per batch, or multiple summaries per batch?**
   - recommendation: start with one summary per 15-item batch for determinism

2. **Should categories be user-defined only, or can the LLM propose them?**
   - recommendation: start user-defined only

3. **Should higher-level summaries be allowed to reference overlapping children?**
   - recommendation: no overlap initially; keep DAG capability in schema, but enforce tree-like compaction first for simpler reasoning

4. **Search backend for multilingual content**
   - recommendation: start with PostgreSQL FTS + trigram; add PGroonga only if real data demands it

5. **Compaction trigger semantics**
   - recommendation: trigger at `>= 15 active items`, compact oldest 15, leave remainder hot

## 17. Recommended First Implementation Slice

If you want the fastest path to a working v0, implement in this order:

1. `pyproject.toml` + `uv` project scaffold
2. SQLAlchemy models and Alembic migration
3. `add_memory()`
4. raw -> leaf summary compaction only
5. `lcm_grep`
6. `lcm_describe`
7. `lcm_expand`
8. higher-order summary compaction
9. `lcm_expand_query`

That gives you a useful system before the full recursive DAG and delegated recall are finished.
