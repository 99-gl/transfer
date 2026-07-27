from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, Request, UploadFile, status

from app.config import get_settings
from app.schemas import GraphSnapshot, ImportPreview, ImportResult
from app.services.excel_converter import convert_excel
from app.services.graph_importer import GraphImporter
from app.services.json_converter import convert_json
from app.services.semantic_search import EmbeddingIndexService, SemanticConfigurationError

router = APIRouter(prefix='/api/imports', tags=['imports'])


async def _content_from_upload(file: UploadFile, allowed_suffixes: tuple[str, ...]) -> bytes:
    if not file.filename or not file.filename.lower().endswith(allowed_suffixes):
        supported = '、'.join(allowed_suffixes)
        raise HTTPException(status_code=422, detail=f'仅支持 {supported} 文件。')
    content = await file.read()
    if not content:
        raise HTTPException(status_code=422, detail='上传文件为空。')
    return content


async def _excel_snapshot(file: UploadFile, sheet: str | None) -> GraphSnapshot:
    try:
        return convert_excel(await _content_from_upload(file, ('.xlsx', '.xlsm')), sheet or None)
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


async def _json_snapshot(file: UploadFile) -> GraphSnapshot:
    try:
        return convert_json(await _content_from_upload(file, ('.json',)))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def _importer(request: Request) -> GraphImporter:
    return GraphImporter(request.app.state.neo4j_driver, request.app.state.neo4j_database)


async def _commit_snapshot(request: Request, snapshot: GraphSnapshot) -> ImportResult:
    result = await _importer(request).sync(snapshot)
    try:
        await EmbeddingIndexService(
            request.app.state.neo4j_driver,
            request.app.state.neo4j_database,
            get_settings(),
        ).rebuild()
    except SemanticConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return result


@router.post('/preview', response_model=ImportPreview)
async def preview_excel_import(
    request: Request,
    file: UploadFile = File(...),
    sheet: str | None = None,
) -> ImportPreview:
    return await _importer(request).preview(await _excel_snapshot(file, sheet))


@router.post('/commit', response_model=ImportResult, status_code=status.HTTP_200_OK)
async def commit_excel_import(
    request: Request,
    file: UploadFile = File(...),
    sheet: str | None = None,
) -> ImportResult:
    return await _commit_snapshot(request, await _excel_snapshot(file, sheet))


@router.post('/json/preview', response_model=ImportPreview)
async def preview_json_import(request: Request, file: UploadFile = File(...)) -> ImportPreview:
    return await _importer(request).preview(await _json_snapshot(file))


@router.post('/json/commit', response_model=ImportResult, status_code=status.HTTP_200_OK)
async def commit_json_import(request: Request, file: UploadFile = File(...)) -> ImportResult:
    return await _commit_snapshot(request, await _json_snapshot(file))
