from __future__ import annotations


def validate_memory_input(fact: str, comment: str, behavior: str) -> None:
    if not fact or not fact.strip():
        raise ValueError("fact cannot be empty")
    if not comment or not comment.strip():
        raise ValueError("comment cannot be empty")
    if not behavior or not behavior.strip():
        raise ValueError("behavior cannot be empty")


def build_content_text(fact: str, comment: str, behavior: str) -> str:
    return f"[FACT] {fact} [COMMENT] {comment} [BEHAVIOR] {behavior}"
