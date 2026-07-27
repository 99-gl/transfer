"""Optional Graphiti setup for future semantic query and extraction features."""

from __future__ import annotations

from graphiti_core import Graphiti
from graphiti_core.cross_encoder.openai_reranker_client import OpenAIRerankerClient
from graphiti_core.embedder.openai import OpenAIEmbedder, OpenAIEmbedderConfig
from graphiti_core.llm_client.config import LLMConfig

from app.clients.think_tag_cleaning import ThinkTagCleaningClient
from app.config import Settings


def create_graphiti(settings: Settings) -> Graphiti:
    """Create Graphiti only when a semantic feature explicitly requests it."""
    required = {
        'LOCAL_LLM_BASE_URL': settings.local_llm_base_url,
        'LOCAL_LLM_MODEL': settings.local_llm_model,
        'LOCAL_EMBED_BASE_URL': settings.local_embed_base_url,
        'LOCAL_EMBED_MODEL': settings.local_embed_model,
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        raise RuntimeError(f'无法启用 Graphiti 语义能力，缺少环境变量：{", ".join(missing)}')

    llm_config = LLMConfig(
        api_key=settings.local_llm_api_key,
        model=settings.local_llm_model,
        base_url=settings.local_llm_base_url,
    )
    llm_client = ThinkTagCleaningClient(config=llm_config, structured_output_mode='json_object')
    embedder = OpenAIEmbedder(
        config=OpenAIEmbedderConfig(
            api_key=settings.local_embed_api_key,
            base_url=settings.local_embed_base_url,
            embedding_model=settings.local_embed_model,
        )
    )
    return Graphiti(
        settings.neo4j_uri,
        settings.neo4j_user,
        settings.neo4j_password,
        llm_client=llm_client,
        embedder=embedder,
        cross_encoder=OpenAIRerankerClient(client=llm_client, config=llm_config),
    )
