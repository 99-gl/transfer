from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


NodeType = Literal['ViolationConcept', 'Phenomenon', 'RootCause']


class GraphNode(BaseModel):
    source_id: str
    uuid: str
    type: NodeType
    name: str
    properties: dict[str, str] = Field(default_factory=dict)


class GraphEdge(BaseModel):
    uuid: str
    source_id: str
    target_id: str
    relation: Literal['has_phenomenon', 'has_root_cause']


class GraphSnapshot(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]


class ImportChanges(BaseModel):
    create_nodes: int
    update_nodes: int
    delete_nodes: int
    create_edges: int
    update_edges: int
    delete_edges: int


class ImportPreview(BaseModel):
    nodes: int
    edges: int
    changes: ImportChanges
    warnings: list[str] = Field(default_factory=list)


class ImportResult(ImportPreview):
    sync_id: str


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=200)
    limit: int = Field(default=20, ge=1, le=100)
    include_neighbors: bool = True


class ApiNode(BaseModel):
    uuid: str
    source_id: str
    name: str
    type: str
    properties: dict[str, Any]
    matched: bool = False


class ApiEdge(BaseModel):
    uuid: str
    source_uuid: str
    target_uuid: str
    relation: str
    properties: dict[str, Any]


class GraphResponse(BaseModel):
    nodes: list[ApiNode]
    edges: list[ApiEdge]
    matched_node_ids: list[str]


class NodeDetail(GraphResponse):
    node: ApiNode
