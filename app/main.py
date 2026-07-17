import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from app.routes.brain import router as brain_router
from app.routes.conversations import router as conversations_router
from config.logging import setup_logging
from config.settings import settings

logger = logging.getLogger("falso")


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    logger.info("Falso API starting up")
    yield
    logger.info("Falso API shutting down")


app = FastAPI(
    title="Falso API",
    version="0.1.0",
    description="Production-grade AI assistant",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(brain_router)
app.include_router(conversations_router)


FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "version": "0.1.0",
        "debug": settings.fastapi_debug,
    }


@app.get("/{full_path:path}")
async def serve_frontend(full_path: str):
    file_path = FRONTEND_DIR / full_path
    if file_path.is_file():
        return FileResponse(str(file_path))
    return FileResponse(str(FRONTEND_DIR / "index.html"))
