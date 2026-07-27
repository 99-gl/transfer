"""Graphiti hybrid retrieval with reciprocal-rank-fusion ordering."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.config import Settings
from app.graphiti_factory import create_graphiti
from app.schemas import GraphResponse
from app.services.semantic_search import SemanticSearchService


class HybridSearchService:
    """Combine Graphiti full-text and vector candidates using RRF."""

    def __init__(self, settings: Settings):
        self.settings = settings

    async def search(self, query: str, limit: int) -> GraphResponse:
        from graphiti_core.search.search_config_recipes import COMBINED_HYBRID_SEARCH_RRF

        graphiti = create_graphiti(self.settings)
        config = deepcopy(COMBINED_HYBRID_SEARCH_RRF)
        config.limit = limit
        try:
            # Direct imports do not otherwise create Graphiti's full-text indices.
            await graphiti.build_indices_and_constraints()
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

            return GraphResponse(
                nodes=[SemanticSearchService._api_node(node) for node in node_map.values()],
                edges=[SemanticSearchService._api_edge(edge) for edge in results.edges],
                matched_node_ids=list(node_map),
            )
        finally:
            await graphiti.close()
