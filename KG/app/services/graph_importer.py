"""Idempotent synchronization of the single Excel-managed graph."""

from __future__ import annotations

from collections import defaultdict
from typing import Any
from uuid import uuid4

from neo4j import AsyncDriver

from app.schemas import GraphEdge, GraphSnapshot, ImportChanges, ImportPreview, ImportResult

MANAGED_BY = 'excel'
GROUP_ID = 'default'
NODE_TYPES = {'ViolationConcept', 'Phenomenon', 'RootCause'}


class GraphImporter:
    def __init__(self, driver: AsyncDriver, database: str):
        self.driver = driver
        self.database = database

    async def preview(self, snapshot: GraphSnapshot) -> ImportPreview:
        node_ids = [node.source_id for node in snapshot.nodes]
        edge_ids = [edge.uuid for edge in snapshot.edges]
        async with self.driver.session(database=self.database) as session:
            existing_nodes = await self._existing_values(
                session,
                '''
                MATCH (n:Entity {managed_by: $managed_by})
                WHERE n.source_id IN $values
                RETURN n.source_id AS value
                ''',
                node_ids,
            )
            existing_edges = await self._existing_values(
                session,
                '''
                MATCH ()-[r:RELATES_TO {managed_by: $managed_by}]-()
                WHERE r.uuid IN $values
                RETURN r.uuid AS value
                ''',
                edge_ids,
            )
            stale_nodes = await self._count_stale_nodes(session, node_ids)
            stale_edges = await self._count_stale_edges(session, edge_ids)

        changes = ImportChanges(
            create_nodes=len(snapshot.nodes) - len(existing_nodes),
            update_nodes=len(existing_nodes),
            delete_nodes=stale_nodes,
            create_edges=len(snapshot.edges) - len(existing_edges),
            update_edges=len(existing_edges),
            delete_edges=stale_edges,
        )
        return ImportPreview(nodes=len(snapshot.nodes), edges=len(snapshot.edges), changes=changes)

    async def sync(self, snapshot: GraphSnapshot) -> ImportResult:
        preview = await self.preview(snapshot)
        sync_id = str(uuid4())
        async with self.driver.session(database=self.database) as session:
            await session.execute_write(self._write_snapshot, snapshot, sync_id)
        return ImportResult(**preview.model_dump(), sync_id=sync_id)

    async def _existing_values(self, session: Any, query: str, values: list[str]) -> set[str]:
        if not values:
            return set()
        result = await session.run(query, managed_by=MANAGED_BY, values=values)
        return {record['value'] async for record in result}

    async def _count_stale_nodes(self, session: Any, source_ids: list[str]) -> int:
        result = await session.run(
            '''
            MATCH (n:Entity {managed_by: $managed_by})
            WHERE NOT n.source_id IN $source_ids
            RETURN count(n) AS count
            ''',
            managed_by=MANAGED_BY,
            source_ids=source_ids,
        )
        record = await result.single()
        return int(record['count']) if record else 0

    async def _count_stale_edges(self, session: Any, edge_ids: list[str]) -> int:
        result = await session.run(
            '''
            MATCH ()-[r:RELATES_TO {managed_by: $managed_by}]-()
            WHERE NOT r.uuid IN $edge_ids
            RETURN count(r) AS count
            ''',
            managed_by=MANAGED_BY,
            edge_ids=edge_ids,
        )
        record = await result.single()
        return int(record['count']) if record else 0

    @staticmethod
    async def _consume(tx: Any, query: str, **parameters: Any) -> None:
        result = await tx.run(query, **parameters)
        await result.consume()

    @classmethod
    async def _write_snapshot(cls, tx: Any, snapshot: GraphSnapshot, sync_id: str) -> None:
        nodes_by_type: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for node in snapshot.nodes:
            if node.type not in NODE_TYPES:
                raise ValueError(f'不支持的节点类型：{node.type}')
            nodes_by_type[node.type].append(cls._node_row(node, sync_id))

        for node_type, rows in nodes_by_type.items():
            # node_type comes from the fixed NODE_TYPES whitelist, never user Cypher.
            await cls._consume(
                tx,
                f'''
                UNWIND $rows AS row
                MERGE (n:Entity {{uuid: row.uuid}})
                ON CREATE SET n.created_at = datetime()
                SET n += row.properties
                SET n:{node_type}
                ''',
                rows=rows,
            )

        edge_rows = [cls._edge_row(edge, snapshot, sync_id) for edge in snapshot.edges]
        if edge_rows:
            await cls._consume(
                tx,
                '''
                UNWIND $rows AS row
                MATCH (source:Entity {uuid: row.source_uuid})
                MATCH (target:Entity {uuid: row.target_uuid})
                MERGE (source)-[r:RELATES_TO {uuid: row.uuid}]->(target)
                ON CREATE SET r.created_at = datetime()
                SET r += row.properties
                ''',
                rows=edge_rows,
            )

        # Edges must go first; stale nodes can then be deleted safely.
        await cls._consume(
            tx,
            '''
            MATCH ()-[r:RELATES_TO {managed_by: $managed_by}]-()
            WHERE r.last_sync_id <> $sync_id
            DELETE r
            ''',
            managed_by=MANAGED_BY,
            sync_id=sync_id,
        )
        await cls._consume(
            tx,
            '''
            MATCH (n:Entity {managed_by: $managed_by})
            WHERE n.last_sync_id <> $sync_id
            DETACH DELETE n
            ''',
            managed_by=MANAGED_BY,
            sync_id=sync_id,
        )

    @staticmethod
    def _node_row(node: GraphNode, sync_id: str) -> dict[str, Any]:
        properties = {
            'uuid': node.uuid,
            'source_id': node.source_id,
            'name': node.name,
            'summary': f'[{node.type}] {node.name}',
            'group_id': GROUP_ID,
            'node_type': node.type,
            'managed_by': MANAGED_BY,
            'last_sync_id': sync_id,
            **node.properties,
        }
        return {'uuid': node.uuid, 'properties': properties}

    @staticmethod
    def _edge_row(edge: GraphEdge, snapshot: GraphSnapshot, sync_id: str) -> dict[str, Any]:
        node_uuids = {node.source_id: node.uuid for node in snapshot.nodes}
        source_uuid = node_uuids.get(edge.source_id)
        target_uuid = node_uuids.get(edge.target_id)
        if source_uuid is None or target_uuid is None:
            raise ValueError(f'关系 {edge.uuid} 引用了不存在的节点。')
        properties = {
            'uuid': edge.uuid,
            'name': edge.relation,
            'fact': f'{edge.source_id} --[{edge.relation}]--> {edge.target_id}',
            'group_id': GROUP_ID,
            'managed_by': MANAGED_BY,
            'last_sync_id': sync_id,
            'source_id': edge.source_id,
            'target_id': edge.target_id,
        }
        return {
            'uuid': edge.uuid,
            'source_uuid': source_uuid,
            'target_uuid': target_uuid,
            'properties': properties,
        }
