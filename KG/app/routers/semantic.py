from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.config import get_settings
from app.schemas import GraphResponse
from app.services.semantic_search import (
    EmbeddingIndexService,
    SemanticConfigurationError,
    SemanticSearchService,
)

router = APIRouter(prefix='/api', tags=['semantic-search'])


class SemanticSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    limit: int = Field(default=10, ge=1, le=50)


class EmbeddingRebuildResult(BaseModel):
    nodes: int
    edges: int


@router.post('/semantic-search', response_model=GraphResponse)
async def semantic_search(request: SemanticSearchRequest) -> GraphResponse:
    try:
        return await SemanticSearchService(get_settings()).search(request.query, request.limit)
    except SemanticConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post('/embeddings/rebuild', response_model=EmbeddingRebuildResult)
async def rebuild_embeddings(request: Request) -> EmbeddingRebuildResult:
    try:
        result = await EmbeddingIndexService(
            request.app.state.neo4j_driver,
            request.app.state.neo4j_database,
            get_settings(),
        ).rebuild()
        return EmbeddingRebuildResult(**result)
    except SemanticConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
