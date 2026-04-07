# RETRIEVAL ENGINE

## OVERVIEW
Four-tool retrieval API: cheap grep, graph-aware describe, budgeted expand, and delegated deep recall.

## STRUCTURE
```
retrieval/
├── grep.py           # FTS + ILIKE search across memories/summaries
├── describe.py       # Subtree manifest via recursive CTE
├── expand.py         # DAG traversal with token cap
└── query_delegate.py # Bounded deep recall (v0: in-process)
```

## WHERE TO LOOK
| Task | File | Key Symbol |
|------|------|------------|
| Change search behavior | `grep.py` | `GrepEngine.grep` |
| Change subtree query | `describe.py` | `DescribeEngine._build_subtree` |
| Change traversal depth/cap | `expand.py` | `ExpandEngine.expand` |
| Change delegation flow | `query_delegate.py` | `QueryDelegate.expand_query` |

## CONVENTIONS
- PostgreSQL FTS via `tsvector @@ plainto_tsquery('english', :q)` with ILIKE fallback
- Recursive CTE uses `WITH RECURSIVE` + text path accumulation for subtree manifests
- Expand tracks `visited` set to prevent DAG cycles
- Token estimation: `len(text) // 4` (simple, no tiktoken dependency in retrieval)
- ExpandItem has `node_type` field: `"summary"` or `"raw_memory"`

## ANTI-PATTERNS
- Never do N+1 queries in describe — use single recursive CTE
- Never skip the visited set in expand — DAGs can have shared nodes
- Never expose `lcm_expand_query` to sub-agents (prevents recursive spawning)
- Never return full content from describe — return manifest only, use expand for detail
