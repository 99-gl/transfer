from fastapi import APIRouter, HTTPException, Request

from app.schemas import GraphResponse, NodeDetail, SearchRequest
from app.services.graph_query import GraphQueryService

router = APIRouter(prefix='/api', tags=['graph'])


def _query_service(request: Request) -> GraphQueryService:
    return GraphQueryService(request.app.state.neo4j_driver, request.app.state.neo4j_database)


@router.post('/search', response_model=GraphResponse)
async def search_graph(request: Request, body: SearchRequest) -> GraphResponse:
    return await _query_service(request).search(body.query, body.limit, body.include_neighbors)


@router.get('/nodes/{uuid}', response_model=NodeDetail)
async def get_node(request: Request, uuid: str) -> NodeDetail:
    detail = await _query_service(request).get_node(uuid)
    if detail is None:
        raise HTTPException(status_code=404, detail='节点不存在。')
    return detail
