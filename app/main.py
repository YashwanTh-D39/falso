import asyncio
import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from app.middleware.security import SecurityMiddleware
from app.routes.agents import router as agents_router
from app.routes.brain import router as brain_router
from app.routes.conversations import router as conversations_router
from app.routes.memory import router as memory_router
from app.routes.system import router as system_router
from app.routes.tools import router as tools_router
from app.routes.voice import router as voice_router
from app.routes.spatial import router as spatial_router
from app.routes.spatial_ws import router as spatial_ws_router, spatial_broadcaster_loop
from app.routes.user_profile import router as user_profile_router
from app.routes.tasks import router as tasks_router
from app.services.proactive_agent import proactive_agent
from app.services.filesystem_indexer import filesystem_indexer
from app.services.boot_tracker import boot_tracker
from config.logging import setup_logging
from config.settings import settings

logger = logging.getLogger("falso")

FRONTEND_ROOT = (Path(__file__).resolve().parent.parent / "frontend").resolve()


def _index_response() -> FileResponse:
    return FileResponse(
        str(FRONTEND_ROOT / "index.html"),
        headers={"Cache-Control": "no-cache"},
    )


from app.services.boot_tracker import boot_tracker


@asynccontextmanager
async def lifespan(app: FastAPI):
    # [1] Configuration
    boot_tracker.start_stage(1)
    setup_logging()
    boot_tracker.end_stage(1)

    # [2] Database
    boot_tracker.start_stage(2)
    try:
        from app.services.filesystem_indexer import filesystem_indexer
        _ = filesystem_indexer.db_manager
        boot_tracker.end_stage(2)
    except Exception as exc:
        boot_tracker.fail_stage(2, str(exc))

    # [3] AI Provider Verification & Model Check
    boot_tracker.start_stage(3)
    prov_name = settings.effective_ai_provider
    if prov_name == "nvidia":
        try:
            from app.routes.brain import brain_service
            verified = False
            if hasattr(brain_service.provider, "verify_model_availability"):
                verified = await brain_service.provider.verify_model_availability()
            if verified:
                msg = f"NVIDIA Model Verified ({brain_service.provider.model})"
            else:
                msg = f"NVIDIA Active ({brain_service.provider.model})"
            boot_tracker.end_stage(3, msg)
        except Exception as exc:
            boot_tracker.end_stage(3, f"NVIDIA Provider Initialized ({exc})")
    elif prov_name == "ollama":
        try:
            import httpx
            async with httpx.AsyncClient(timeout=3.0) as client:
                res = await client.get(f"{settings.ollama_base_url}/api/tags")
                if res.status_code == 200:
                    async def _warmup():
                        try:
                            from app.routes.brain import brain_service
                            if hasattr(brain_service.provider, "warm"):
                                await brain_service.provider.warm()
                        except Exception:
                            pass
                    asyncio.create_task(_warmup())
                    msg = f"Ollama Warm & Online ({settings.ollama_model})"
                else:
                    msg = f"HTTP {res.status_code}"
                boot_tracker.end_stage(3, msg)
        except Exception as exc:
            boot_tracker.end_stage(3, f"Ollama Offline ({exc})")
    else:
        boot_tracker.end_stage(3, f"Provider: {prov_name}")

    # [4] Voice
    boot_tracker.start_stage(4)
    try:
        from app.routes.voice import voice_service
        _ = voice_service
        boot_tracker.end_stage(4)
    except Exception as exc:
        boot_tracker.fail_stage(4, str(exc))

    # [5] Web Intelligence
    boot_tracker.start_stage(5)
    try:
        from app.routes.brain import brain_service
        _ = brain_service
        boot_tracker.end_stage(5, "Tools Registered")
    except Exception as exc:
        boot_tracker.fail_stage(5, str(exc))

    # [6] Filesystem Indexer (Non-blocking background async start)
    boot_tracker.start_stage(6)
    if settings.enable_filesystem_indexer:
        asyncio.create_task(asyncio.to_thread(filesystem_indexer.start))
        boot_tracker.end_stage(6, "Background Async Start")
    else:
        boot_tracker.end_stage(6, "Disabled by Flag")

    # [7] Spatial Service (Non-blocking background async start)
    boot_tracker.start_stage(7)
    if settings.enable_spatial_os:
        asyncio.create_task(spatial_broadcaster_loop())
        asyncio.create_task(proactive_agent.start_monitoring_loop())
        boot_tracker.end_stage(7, "Background Async Start")
    else:
        boot_tracker.end_stage(7, "Disabled by Flag")

    # [8] WebSocket
    boot_tracker.start_stage(8)
    try:
        from app.routes.spatial_ws import ws_manager
        _ = ws_manager
        boot_tracker.end_stage(8)
    except Exception as exc:
        boot_tracker.fail_stage(8, str(exc))

    # [9] Living Orb
    boot_tracker.start_stage(9)
    boot_tracker.end_stage(9, "Awaiting Frontend Handshake")

    # Keep-alive pin for the local LLM: cheap warm pings every 5 minutes keep
    # the model resident so every user chat starts from a warm first token
    # (guards against `ollama stop` / Ollama restarts mid-session).
    keep_alive_pinned = False

    async def _ollama_keepalive_loop():
        nonlocal keep_alive_pinned
        while True:
            try:
                from app.routes.brain import brain_service
                was_pinned = keep_alive_pinned
                keep_alive_pinned = await brain_service.provider.warm()
                if not was_pinned and keep_alive_pinned:
                    logger.info("Ollama model pinned warm (keep-alive loop)")
            except Exception as exc:
                logger.debug("Ollama keep-alive info: %s", exc)
            await asyncio.sleep(300)

    if settings.ai_provider == "ollama":
        asyncio.create_task(_ollama_keepalive_loop())

    logger.info("Falso Core API booted successfully — ready for frontend connection.")

    try:
        yield
    finally:
        if settings.enable_filesystem_indexer:
            filesystem_indexer.stop()

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

app.include_router(agents_router)
app.include_router(brain_router)
app.include_router(conversations_router)
app.include_router(memory_router)
app.include_router(tools_router)
app.include_router(system_router)
app.include_router(voice_router)
app.include_router(spatial_router)
app.include_router(spatial_ws_router)
app.include_router(user_profile_router)
app.include_router(tasks_router)


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
