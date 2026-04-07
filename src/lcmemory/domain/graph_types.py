from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from lcmemory.domain.schemas import SubtreeNode


class SubtreeManifest(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    nodes: list[SubtreeNode]
    total_nodes: int
    total_tokens: int
    max_depth: int


class GraphPath(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    node_ids: list[str]


class DAGEdge(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    source_id: str
    target_id: str
    edge_type: str
