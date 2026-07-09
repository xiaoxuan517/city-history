from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.errors import register_error_handlers
from app.api.rate_limit import enforce_rate_limit
from app.api.v1.alist import router as alist_router
from app.api.v1.assistant import router as assistant_router
from app.api.v1.auth import router as auth_router
from app.api.v1.chat import router as chat_router
from app.api.v1.documents import router as document_router
from app.api.v1.gazetteer_files import router as gazetteer_file_router
from app.api.v1.knowledge_bases import router as knowledge_base_router
from app.api.v1.old_pictures import router as old_picture_router
from app.api.v1.prompts import router as prompt_router
from app.api.v1.system import router as system_router
from app.config.settings import settings
from app.config.logging_setup import setup_logging
from app.services.gazetteer_file_scheduler import run_gazetteer_file_sync_loop
from app.services.old_picture_scheduler import run_old_picture_sync_loop

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
FRONTEND_DIST_DIR = PROJECT_ROOT / "frontend" / "dist"


@asynccontextmanager
async def lifespan(_: FastAPI):
    setup_logging()
    sync_tasks = []
    if settings.gazetteer_file_sync_enabled:
        sync_tasks.append(asyncio.create_task(run_gazetteer_file_sync_loop()))
    if settings.old_picture_sync_enabled:
        sync_tasks.append(asyncio.create_task(run_old_picture_sync_loop()))
    try:
        yield
    finally:
        for sync_task in sync_tasks:
            sync_task.cancel()
        for sync_task in sync_tasks:
            try:
                await sync_task
            except asyncio.CancelledError:
                pass


app = FastAPI(title="LangChain RAG API", version="0.1.0", lifespan=lifespan)
register_error_handlers(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(system_router)
app.include_router(alist_router, dependencies=[Depends(enforce_rate_limit)])
app.include_router(gazetteer_file_router, dependencies=[Depends(enforce_rate_limit)])
app.include_router(auth_router, dependencies=[Depends(enforce_rate_limit)])
app.include_router(knowledge_base_router, dependencies=[Depends(enforce_rate_limit)])
app.include_router(old_picture_router, dependencies=[Depends(enforce_rate_limit)])
app.include_router(document_router, dependencies=[Depends(enforce_rate_limit)])
app.include_router(chat_router, dependencies=[Depends(enforce_rate_limit)])
app.include_router(prompt_router, dependencies=[Depends(enforce_rate_limit)])
app.include_router(assistant_router, dependencies=[Depends(enforce_rate_limit)])


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(FRONTEND_DIST_DIR / "index.html")


@app.get("/login", include_in_schema=False)
def login_index() -> FileResponse:
    return FileResponse(FRONTEND_DIST_DIR / "index.html")


@app.get("/workspace", include_in_schema=False)
def workspace_index() -> FileResponse:
    return FileResponse(FRONTEND_DIST_DIR / "index.html")


@app.get("/workspace/{_:path}", include_in_schema=False)
def workspace_detail_index(_: str) -> FileResponse:
    return FileResponse(FRONTEND_DIST_DIR / "index.html")


@app.get("/gazetteers", include_in_schema=False)
def gazetteers_index() -> FileResponse:
    return FileResponse(FRONTEND_DIST_DIR / "index.html")


@app.get("/assistant", include_in_schema=False)
def assistant_index() -> FileResponse:
    return FileResponse(FRONTEND_DIST_DIR / "index.html")


@app.get("/history-album", include_in_schema=False)
def history_album_index() -> FileResponse:
    return FileResponse(FRONTEND_DIST_DIR / "index.html")


@app.get("/favorites", include_in_schema=False)
def favorites_index() -> FileResponse:
    return FileResponse(FRONTEND_DIST_DIR / "index.html")


if FRONTEND_DIST_DIR.exists():
    app.mount("/", StaticFiles(directory=FRONTEND_DIST_DIR, html=True), name="frontend")
