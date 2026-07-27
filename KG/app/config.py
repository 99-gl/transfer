from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    neo4j_uri: str = 'bolt://localhost:7687'
    neo4j_user: str = 'neo4j'
    neo4j_password: str = 'password'
    neo4j_database: str = 'neo4j'

    # Kept separate from the import/query path. They are required only when
    # Graphiti semantic retrieval or LLM extraction is enabled later.
    local_llm_base_url: str | None = None
    local_llm_model: str | None = None
    local_llm_api_key: str = 'dummy-key'
    local_embed_base_url: str | None = None
    local_embed_model: str | None = None
    local_embed_api_key: str = 'dummy-key'

    model_config = SettingsConfigDict(env_file='.env', extra='ignore')


@lru_cache
def get_settings() -> Settings:
    return Settings()
