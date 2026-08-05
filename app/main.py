import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from app.middleware.security import SecurityMiddleware
from app.routes.brain import router as brain_router
from app.routes.conversations import router as conversations_router
from app.routes.memory import router as memory_router
from app.routes.system import router as system_router
from app.routes.tools import router as tools_router
from app.routes.voice import router as voice_router
from app.services.system_monitor import system_monitor
from config.logging import setup_logging
from config.settings import settings

logger = logging.getLogger("falso")

FRONTEND_ROOT = (Path(__file__).resolve().parent.parent / "frontend").resolve()


def _index_response() -> FileResponse:
    return FileResponse(
        str(FRONTEND_ROOT / "index.html"),
        headers={"Cache-Control": "no-cache"},
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    system_monitor.start()
    logger.info("Falso API starting up")
    try:
        yield
    finally:
        await system_monitor.stop()

        # Close AI provider HTTP client if it exposes aclose()
        from app.routes.brain import brain_service
        provider = brain_service.provider
        if hasattr(provider, "aclose"):
            await provider.aclose()

        logger.info("Falso API shutting down")




app = FastAPI(
    title="Falso API",
    version="0.1.0",
    description="Production-grade AI assistant",
    lifespan=lifespan,
)

# Middleware order: last added = outermost. CORS runs outside SecurityMiddleware
# so preflight responses also get security headers.
app.add_middleware(SecurityMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Falso-Token"],
)

app.include_router(brain_router)
app.include_router(conversations_router)
app.include_router(memory_router)
app.include_router(tools_router)
app.include_router(system_router)
app.include_router(voice_router)


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "version": "0.1.0",
        "debug": settings.fastapi_debug,
    }


@app.get("/{full_path:path}")
async def serve_frontend(full_path: str):
    if not full_path:
        return _index_response()

    # Unknown /api/* paths must never be served the SPA (API clients expect
    # JSON 404, not 200 HTML). The security middleware still guards auth and
    # body limits for these paths before we get here.
    if full_path == "api" or full_path.startswith("api/"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Not Found",
        )

    try:
        candidate = (FRONTEND_ROOT / full_path).resolve()
        candidate.relative_to(FRONTEND_ROOT)
    except ValueError:
        return _index_response()

    if candidate.is_file():
        return FileResponse(
            str(candidate),
            headers={"Cache-Control": "public, max-age=3600"},
        )
    return _index_response()
