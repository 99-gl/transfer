"""Convert the legacy node/edge JSON format into the workbench graph snapshot."""

from __future__ import annotations

import json
from typing import Any

from app.schemas import GraphEdge, GraphNode, GraphSnapshot
from app.services.excel_converter import stable_uuid

NODE_TYPES = {'ViolationConcept', 'Phenomenon', 'RootCause'}
RELATIONS = {'has_phenomenon', 'has_root_cause'}


def convert_json(content: bytes) -> GraphSnapshot:
    """Parse legacy ``nodes`` / ``edges`` JSON without changing its public format."""
    try:
        payload = json.loads(content.decode('utf-8'))
    except UnicodeDecodeError as exc:
        raise ValueError('JSON 文件必须使用 UTF-8 编码。') from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f'JSON 解析失败：{exc.msg}（第 {exc.lineno} 行）。') from exc

    if not isinstance(payload, dict):
        raise ValueError('JSON 顶层必须是包含 nodes 和 edges 的对象。')
    raw_nodes = payload.get('nodes')
    raw_edges = payload.get('edges')
    if not isinstance(raw_nodes, list) or not isinstance(raw_edges, list):
        raise ValueError('JSON 必须包含 nodes 数组和 edges 数组。')

    nodes: list[GraphNode] = []
    source_ids: dict[str, str] = {}
    for position, raw_node in enumerate(raw_nodes, start=1):
        if not isinstance(raw_node, dict):
            raise ValueError(f'nodes[{position}] 必须是对象。')
        raw_id = _required_text(raw_node.get('id'), f'nodes[{position}].id')
        node_type = _required_text(raw_node.get('type'), f'nodes[{position}].type')
        if node_type not in NODE_TYPES:
            raise ValueError(f'nodes[{position}].type 不支持：{node_type!r}。')
        if raw_id in source_ids:
            raise ValueError(f'节点 id 重复：{raw_id!r}。')
        properties = _properties(raw_node.get('properties'), f'nodes[{position}].properties')
        name = properties.get('name') or properties.get('scenario_id') or raw_id
        source_id = f'json:{node_type}:{raw_id}'
        source_ids[raw_id] = source_id
        nodes.append(
            GraphNode(
                source_id=source_id,
                uuid=stable_uuid('node', source_id),
                type=node_type,
                name=name,
                properties={**properties, 'json_id': raw_id},
            )
        )

    edges: list[GraphEdge] = []
    edge_ids: set[str] = set()
    for position, raw_edge in enumerate(raw_edges, start=1):
        if not isinstance(raw_edge, dict):
            raise ValueError(f'edges[{position}] 必须是对象。')
        source = _required_text(raw_edge.get('source'), f'edges[{position}].source')
        target = _required_text(raw_edge.get('target'), f'edges[{position}].target')
        relation = _required_text(raw_edge.get('relation'), f'edges[{position}].relation')
        if relation not in RELATIONS:
            raise ValueError(f'edges[{position}].relation 不支持：{relation!r}。')
        if source not in source_ids or target not in source_ids:
            raise ValueError(f'edges[{position}] 引用了不存在的节点。')
        source_id = source_ids[source]
        target_id = source_ids[target]
        edge_key = f'{relation}:{source_id}:{target_id}'
        edge_uuid = stable_uuid('edge', edge_key)
        if edge_uuid in edge_ids:
            raise ValueError(f'edges[{position}] 与前面的关系重复。')
        edge_ids.add(edge_uuid)
        edges.append(
            GraphEdge(
                uuid=edge_uuid,
                source_id=source_id,
                target_id=target_id,
                relation=relation,
            )
        )

    if not nodes:
        raise ValueError('JSON 中没有可导入的节点。')
    return GraphSnapshot(nodes=nodes, edges=edges)


def _required_text(value: Any, field_name: str) -> str:
    if value is None or not str(value).strip():
        raise ValueError(f'{field_name} 不能为空。')
    return str(value).strip()


def _properties(value: Any, field_name: str) -> dict[str, str]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f'{field_name} 必须是对象。')
    result: dict[str, str] = {}
    for key, item in value.items():
        if not isinstance(key, str):
            raise ValueError(f'{field_name} 的属性名必须是字符串。')
        if isinstance(item, (dict, list)):
            raise ValueError(f'{field_name}.{key} 仅支持字符串、数字、布尔值或空值。')
        result[key] = '' if item is None else str(item)
    return result
