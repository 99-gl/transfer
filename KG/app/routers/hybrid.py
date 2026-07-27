from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.config import get_settings
from app.schemas import GraphResponse
from app.services.hybrid_search import HybridSearchService

router = APIRouter(prefix='/api', tags=['hybrid-search'])


class HybridSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    limit: int = Field(default=10, ge=1, le=50)


@router.post('/hybrid-search', response_model=GraphResponse)
async def hybrid_search(request: HybridSearchRequest) -> GraphResponse:
    return await HybridSearchService(get_settings()).search(request.query, request.limit)
