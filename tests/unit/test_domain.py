from __future__ import annotations

from lcmemory.compaction.policy import CompactionPlan, CompactionPolicy, should_compact
from lcmemory.domain.enums import CompactionSourceType
from lcmemory.ingestion.validators import build_content_text, validate_memory_input


def test_should_compact_below_threshold():
    policy = CompactionPolicy(threshold=15)
    assert not should_compact(14, policy)


def test_should_compact_at_threshold():
    policy = CompactionPolicy(threshold=15)
    assert should_compact(15, policy)


def test_should_compact_above_threshold():
    policy = CompactionPolicy(threshold=15)
    assert should_compact(20, policy)


def test_default_policy_threshold():
    policy = CompactionPolicy()
    assert policy.threshold == 15
    assert policy.trigger_mode == "oldest_first"
    assert policy.max_retries == 3


def test_compaction_plan_fields():
    from uuid import uuid4

    plan = CompactionPlan(
        category_id=uuid4(),
        source_type=CompactionSourceType.RAW,
        batch_size=15,
        level=0,
    )
    assert plan.batch_size == 15
    assert plan.level == 0


def test_validate_memory_input_valid():
    validate_memory_input("fact", "comment", "behavior")


def test_validate_memory_input_empty_fact():
    import pytest

    with pytest.raises(ValueError):
        validate_memory_input("", "comment", "behavior")


def test_validate_memory_input_whitespace_comment():
    import pytest

    with pytest.raises(ValueError):
        validate_memory_input("fact", "   ", "behavior")


def test_build_content_text():
    result = build_content_text("a fact", "a comment", "a behavior")
    assert "a fact" in result
    assert "a comment" in result
    assert "a behavior" in result


def test_add_memory_request_validation():
    from lcmemory.domain.schemas import AddMemoryRequest

    req = AddMemoryRequest(
        category_name="test",
        fact="fact",
        comment="comment",
        behavior="behavior",
    )
    assert req.category_name == "test"


def test_add_memory_request_rejects_empty():
    import pytest
    from pydantic import ValidationError

    from lcmemory.domain.schemas import AddMemoryRequest

    with pytest.raises(ValidationError):
        AddMemoryRequest(category_name="", fact="f", comment="c", behavior="b")


def test_grep_params_defaults():
    from lcmemory.domain.schemas import GrepParams

    params = GrepParams(pattern="test")
    assert params.mode == "full_text"
    assert params.scope == "both"
    assert params.limit == 20
    assert params.category is None


def test_expand_params_defaults():
    from lcmemory.domain.schemas import ExpandParams

    params = ExpandParams(summary_ids=["abc"])
    assert params.max_depth == 3
    assert params.include_messages is True
    assert params.token_cap == 12000


def test_memory_snippet_creation():
    from lcmemory.domain.schemas import MemorySnippet

    snippet = MemorySnippet(
        id="raw_123",
        node_type="raw_memory",
        category="auth",
        snippet="Use JWT tokens",
    )
    assert snippet.level is None


def test_tool_definitions_exist():
    from lcmemory.tools.contracts import TOOL_DEFINITIONS

    names = {t.name for t in TOOL_DEFINITIONS}
    assert "lcm_grep" in names
    assert "lcm_describe" in names
    assert "lcm_expand" in names
    assert "lcm_expand_query" in names


def test_graph_types():
    from lcmemory.domain.graph_types import DAGEdge, GraphPath, SubtreeManifest
    from lcmemory.domain.schemas import SubtreeNode

    path = GraphPath(node_ids=["a", "b", "c"])
    assert len(path.node_ids) == 3

    edge = DAGEdge(source_id="a", target_id="b", edge_type="parent_link")
    assert edge.edge_type == "parent_link"

    manifest = SubtreeManifest(
        nodes=[
            SubtreeNode(
                id="a",
                depth_from_root=0,
                path="",
                child_count=2,
                descendant_raw_count=15,
                token_count=100,
            )
        ],
        total_nodes=1,
        total_tokens=100,
        max_depth=0,
    )
    assert manifest.total_nodes == 1
