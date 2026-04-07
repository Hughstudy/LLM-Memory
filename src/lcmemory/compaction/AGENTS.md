# COMPACTION SUBSYSTEM

## OVERVIEW
LLM-driven summarization pipeline that converts raw memories into level-0 leaf summaries, then recursively condenses summaries into higher-level nodes.

## STRUCTURE
```
compaction/
├── policy.py       # Rules + CompactionPlan dataclass
├── selector.py     # Batch selection (oldest-first)
├── prompts.py      # System/user prompt builders
├── llm_client.py   # OpenAI-compatible chat via httpx
└── service.py      # Orchestrator: raw→leaf + summary→condensed
```

## WHERE TO LOOK
| Task | File | Key Symbol |
|------|------|------------|
| Change threshold | `policy.py` | `CompactionPolicy.threshold` |
| Change batch ordering | `selector.py` | `CompactionSelector.select_raw_batch` |
| Change LLM prompt | `prompts.py` | `RAW_COMPACTION_SYSTEM_PROMPT` |
| Change LLM provider | `llm_client.py` | `LLMClient.__init__` |
| Add new compaction flow | `service.py` | `CompactionService` |

## CONVENTIONS
- Prompts request JSON output with keys: `title`, `summary_text`, `fact_summary`, `comment_summary`, `behavior_summary`
- All three summary channels are always populated (empty string + metadata if absent, never dropped)
- Compaction jobs are tracked in `compaction_jobs` table for auditability
- Failed jobs record `error_text` and stay in `FAILED` status

## ANTI-PATTERNS
- Never physically delete source data — only update `compaction_status`
- Never compact across categories (enforced by selector)
- Never mix partially failed batches (job-level atomicity)
- Never hold a DB session across the LLM call boundary
