"""Read-only graph queries used by the workbench UI."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from neo4j import AsyncDriver

from app.schemas import ApiEdge, ApiNode, GraphResponse, NodeDetail

HIDDEN_PROPERTIES = {'name_embedding', 'fact_embedding'}


class GraphQueryService:
    def __init__(self, driver: AsyncDriver, database: str):
        self.driver = driver
        self.database = database

    async def search(self, query: str, limit: int, include_neighbors: bool) -> GraphResponse:
        async with self.driver.session(database=self.database) as session:
            result = await session.run(
                '''
                MATCH (n:Entity {managed_by: 'excel'})
                WHERE toLower(n.name) CONTAINS toLower($search_text)
                   OR toLower(n.source_id) CONTAINS toLower($search_text)
                   OR toLower(coalesce(n.summary, '')) CONTAINS toLower($search_text)
                   OR toLower(coalesce(n.identification_method, '')) CONTAINS toLower($search_text)
                RETURN n
                ORDER BY n.name
                LIMIT $limit
                ''',
                search_text=query.strip(),
                limit=limit,
            )
            matched_nodes = [self._node_from_db(record['n'], matched=True) async for record in result]
            if not matched_nodes:
                return GraphResponse(nodes=[], edges=[], matched_node_ids=[])
            return await self._with_neighbors(session, matched_nodes, include_neighbors)

    async def get_node(self, uuid: str) -> NodeDetail | None:
        async with self.driver.session(database=self.database) as session:
            result = await session.run(
                'MATCH (n:Entity {uuid: $uuid}) RETURN n',
                uuid=uuid,
            )
            record = await result.single()
            if record is None:
                return None
            node = self._node_from_db(record['n'], matched=True)
            graph = await self._with_neighbors(session, [node], include_neighbors=True)
            return NodeDetail(node=node, **graph.model_dump())

    async def _with_neighbors(
        self,
        session: Any,
        matched_nodes: list[ApiNode],
        include_neighbors: bool,
    ) -> GraphResponse:
        nodes = {node.uuid: node for node in matched_nodes}
        edges: dict[str, ApiEdge] = {}
        if include_neighbors:
            result = await session.run(
                '''
                MATCH (left:Entity)-[r:RELATES_TO]-(right:Entity)
                WHERE left.uuid IN $selected OR right.uuid IN $selected
                RETURN left, r, right, startNode(r).uuid AS source_uuid, endNode(r).uuid AS target_uuid
                ''',
                selected=list(nodes),
            )
            async for record in result:
                for key in ('left', 'right'):
                    candidate = self._node_from_db(record[key], matched=record[key]['uuid'] in nodes)
                    existing = nodes.get(candidate.uuid)
                    if existing is None or candidate.matched:
                        nodes[candidate.uuid] = candidate
                edge = self._edge_from_db(record['r'], record['source_uuid'], record['target_uuid'])
                edges[edge.uuid] = edge

        return GraphResponse(
            nodes=list(nodes.values()),
            edges=list(edges.values()),
            matched_node_ids=[node.uuid for node in matched_nodes],
        )

    @classmethod
    def _node_from_db(cls, node: Any, matched: bool) -> ApiNode:
        properties = cls._properties(dict(node))
        return ApiNode(
            uuid=str(properties['uuid']),
            source_id=str(properties.get('source_id', '')),
            name=str(properties.get('name', '')),
            type=str(properties.get('node_type', 'Entity')),
            properties=properties,
            matched=matched,
        )

    @classmethod
    def _edge_from_db(cls, edge: Any, source_uuid: str, target_uuid: str) -> ApiEdge:
        properties = cls._properties(dict(edge))
        return ApiEdge(
            uuid=str(properties['uuid']),
            source_uuid=str(source_uuid),
            target_uuid=str(target_uuid),
            relation=str(properties.get('name', 'RELATES_TO')),
            properties=properties,
        )

    @classmethod
    def _properties(cls, source: Mapping[str, Any]) -> dict[str, Any]:
        return {
            key: cls._json_value(value)
            for key, value in source.items()
            if key not in HIDDEN_PROPERTIES
        }

    @classmethod
    def _json_value(cls, value: Any) -> Any:
        if isinstance(value, Mapping):
            return {key: cls._json_value(item) for key, item in value.items()}
        if isinstance(value, list):
            return [cls._json_value(item) for item in value]
        iso_format = getattr(value, 'iso_format', None)
        if callable(iso_format):
            return iso_format()
        return value
