from __future__ import annotations

from typing import Any

RAW_COMPACTION_SYSTEM_PROMPT = (
    "You are an expert at analyzing and summarizing raw memory entries. "
    "Your task is to identify patterns, common themes, and extract key "
    "information from a batch of memory entries.\n\n"
    "For each batch of memories provided, you must:\n"
    "1. Identify common patterns and themes\n"
    "2. Extract the most important facts, comments, and behaviors\n"
    "3. Create a concise but comprehensive summary\n\n"
    "You must respond with a JSON object containing exactly these keys:\n"
    '- "title": A brief descriptive title for this summary (max 10 words)\n'
    '- "summary_text": A comprehensive summary of all the memories '
    "(2-3 sentences)\n"
    '- "fact_summary": A consolidated summary of the key facts\n'
    '- "comment_summary": A consolidated summary of the comments\n'
    '- "behavior_summary": A consolidated summary of the behaviors\n\n'
    "Be precise and avoid redundancy while preserving all important "
    "information."
)

SUMMARY_COMPACTION_SYSTEM_PROMPT = (
    "You are an expert at condensing and synthesizing summary information. "
    "Your task is to take multiple related summaries and create a "
    "higher-level summary that captures the essential information.\n\n"
    "For each batch of summaries provided, you must:\n"
    "1. Identify common themes and patterns across summaries\n"
    "2. Consolidate overlapping information\n"
    "3. Create a more abstract but still informative summary\n\n"
    "You must respond with a JSON object containing exactly these keys:\n"
    '- "title": A brief descriptive title for this consolidated summary '
    "(max 10 words)\n"
    '- "summary_text": A consolidated summary that captures the essence '
    "of all input summaries (2-3 sentences)\n"
    '- "fact_summary": A consolidated summary of the key facts across '
    "all summaries\n"
    '- "comment_summary": A consolidated summary of the comments across '
    "all summaries\n"
    '- "behavior_summary": A consolidated summary of the behaviors '
    "across all summaries\n\n"
    "Maintain important details while reducing redundancy and increasing "
    "abstraction."
)


def build_raw_compaction_messages(memories: list[dict[str, Any]]) -> list[dict[str, str]]:
    import json

    memories_json = json.dumps(memories, indent=2)
    return [
        {"role": "system", "content": RAW_COMPACTION_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"Please summarize the following {len(memories)} memory entries:\n\n{memories_json}"
            ),
        },
    ]


def build_summary_compaction_messages(
    summaries: list[dict[str, Any]],
) -> list[dict[str, str]]:
    import json

    summaries_json = json.dumps(summaries, indent=2)
    return [
        {"role": "system", "content": SUMMARY_COMPACTION_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"Please consolidate the following {len(summaries)} summaries:\n\n{summaries_json}"
            ),
        },
    ]
