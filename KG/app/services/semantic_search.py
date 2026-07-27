"""Embedding indexing and Graphiti-backed semantic search."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from neo4j import AsyncDriver

from app.config import Settings
from app.graphiti_factory import create_graphiti
from app.schemas import ApiEdge, ApiNode, GraphResponse

EMBEDDING_BATCH_SIZE = 64


class SemanticConfigurationError(RuntimeError):
    """Raised when the embedding endpoint has not been configured."""


class EmbeddingIndexService:
    """Creates embeddings for graph records managed by the Excel synchronizer."""

    def __init__(self, driver: AsyncDriver, database: str, settings: Settings):
        self.driver = driver
        self.database = database
        self.settings = settings

    async def rebuild(self) -> dict[str, int]:
        embedder = self._create_embedder()
        async with self.driver.session(database=self.database) as session:
            node_result = await session.run(
                '''
                MATCH (n:Entity {managed_by: 'excel'})
                RETURN n.uuid AS uuid, n.summary AS text
                ORDER BY n.uuid
                '''
            )
            nodes = [dict(record) async for record in node_result]
            edge_result = await session.run(
                '''
                MATCH ()-[r:RELATES_TO {managed_by: 'excel'}]->()
                RETURN r.uuid AS uuid, r.fact AS text
                ORDER BY r.uuid
                '''
            )
            edges = [dict(record) async for record in edge_result]

            node_rows = await self._embed_rows(embedder, nodes)
            edge_rows = await self._embed_rows(embedder, edges)
            if node_rows:
                await session.execute_write(self._write_node_embeddings, node_rows)
            if edge_rows:
                await session.execute_write(self._write_edge_embeddings, edge_rows)
        return {'nodes': len(node_rows), 'edges': len(edge_rows)}

    def _create_embedder(self):
        if not self.settings.local_embed_base_url or not self.settings.local_embed_model:
            raise SemanticConfigurationError(
                '语义检索需要配置 LOCAL_EMBED_BASE_URL 和 LOCAL_EMBED_MODEL。'
            )
        from graphiti_core.embedder.openai import OpenAIEmbedder, OpenAIEmbedderConfig

        return OpenAIEmbedder(
            config=OpenAIEmbedderConfig(
                api_key=self.settings.local_embed_api_key,
                base_url=self.settings.local_embed_base_url,
                embedding_model=self.settings.local_embed_model,
            )
        )

    async def _embed_rows(self, embedder: Any, rows: list[dict[str, str]]) -> list[dict[str, Any]]:
        embedded: list[dict[str, Any]] = []
        for chunk in _chunks(rows, EMBEDDING_BATCH_SIZE):
            vectors = await embedder.create_batch([row['text'] or '' for row in chunk])
            embedded.extend(
                {'uuid': row['uuid'], 'embedding': vector} for row, vector in zip(chunk, vectors, strict=True)
            )
        return embedded

    @staticmethod
    async def _write_node_embeddings(tx: Any, rows: list[dict[str, Any]]) -> None:
        result = await tx.run(
            '''
            UNWIND $rows AS row
            MATCH (n:Entity {uuid: row.uuid})
            SET n.name_embedding = row.embedding
            ''',
            rows=rows,
        )
        await result.consume()

    @staticmethod
    async def _write_edge_embeddings(tx: Any, rows: list[dict[str, Any]]) -> None:
        result = await tx.run(
            '''
            UNWIND $rows AS row
            MATCH ()-[r:RELATES_TO {uuid: row.uuid}]->()
            SET r.fact_embedding = row.embedding
            ''',
            rows=rows,
        )
        await result.consume()


class SemanticSearchService:
    """Uses Graphiti similarity search and returns UI-ready graph data."""

    def __init__(self, settings: Settings):
        self.settings = settings

    async def search(self, query: str, limit: int) -> GraphResponse:
        from graphiti_core.search.search_config import (
            EdgeReranker,
            EdgeSearchConfig,
            EdgeSearchMethod,
            NodeReranker,
            NodeSearchConfig,
            NodeSearchMethod,
            SearchConfig,
        )

        graphiti = create_graphiti(self.settings)
        config = SearchConfig(
            edge_config=EdgeSearchConfig(
                search_methods=[EdgeSearchMethod.cosine_similarity],
                reranker=EdgeReranker.rrf,
            ),
            node_config=NodeSearchConfig(
                search_methods=[NodeSearchMethod.cosine_similarity],
                reranker=NodeReranker.rrf,
            ),
            limit=limit,
        )
        try:
            results = await graphiti.search_(query, config=config, group_ids=['default'])
            node_map = {node.uuid: node for node in results.nodes}
            edge_node_ids = {
                node_uuid
                for edge in results.edges
                for node_uuid in (edge.source_node_uuid, edge.target_node_uuid)
            }
            missing_node_ids = list(edge_node_ids - set(node_map))
            if missing_node_ids:
                for node in await graphiti.nodes.entity.get_by_uuids(missing_node_ids):
                    node_map[node.uuid] = node

            matched_node_ids = list(set(node_map))
            return GraphResponse(
                nodes=[self._api_node(node) for node in node_map.values()],
                edges=[self._api_edge(edge) for edge in results.edges],
                matched_node_ids=matched_node_ids,
            )
        finally:
            await graphiti.close()

    @staticmethod
    def _api_node(node: Any) -> ApiNode:
        properties = {
            'uuid': node.uuid,
            'name': node.name,
            'summary': node.summary,
            'group_id': node.group_id,
            **(node.attributes or {}),
        }
        labels = [label for label in node.labels if label != 'Entity']
        return ApiNode(
            uuid=node.uuid,
            source_id=str(properties.get('source_id', '')),
            name=node.name,
            type=labels[0] if labels else str(properties.get('node_type', 'Entity')),
            properties=properties,
            matched=True,
        )

    @staticmethod
    def _api_edge(edge: Any) -> ApiEdge:
        properties = {
            'uuid': edge.uuid,
            'name': edge.name,
            'fact': edge.fact,
            'group_id': edge.group_id,
            **(edge.attributes or {}),
        }
        return ApiEdge(
            uuid=edge.uuid,
            source_uuid=edge.source_node_uuid,
            target_uuid=edge.target_node_uuid,
            relation=edge.name,
            properties=properties,
        )


def _chunks(values: list[dict[str, str]], size: int) -> Iterable[list[dict[str, str]]]:
    for start in range(0, len(values), size):
        yield values[start : start + size]
