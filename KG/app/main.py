from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from neo4j import AsyncGraphDatabase

from app.config import get_settings
from app.routers import graph, imports, semantic

ROOT_DIR = Path(__file__).resolve().parent.parent
WEB_DIR = ROOT_DIR / 'web'


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    driver = AsyncGraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_user, settings.neo4j_password),
    )
    await driver.verify_connectivity()
    app.state.neo4j_driver = driver
    app.state.neo4j_database = settings.neo4j_database
    try:
        yield
    finally:
        await driver.close()


app = FastAPI(title='EDA Knowledge Graph Workbench', version='0.1.0', lifespan=lifespan)
app.include_router(imports.router)
app.include_router(graph.router)
app.include_router(semantic.router)
app.mount('/assets', StaticFiles(directory=str(WEB_DIR)), name='assets')


@app.get('/', include_in_schema=False)
async def workbench() -> FileResponse:
    return FileResponse(WEB_DIR / 'index.html')


@app.get('/healthcheck')
async def healthcheck() -> dict[str, str]:
    return {'status': 'healthy'}
