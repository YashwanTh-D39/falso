import logging

from fastapi import APIRouter
from pydantic import BaseModel

from app.services.system_monitor import system_monitor

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/system", tags=["System"])


@router.get("/stats")
async def get_system_stats():
    """All metrics are sampled in the background by SystemMonitor; the request
    path is a single O(1) cache read with zero threads and zero blocking."""
    return system_monitor.stats


@router.get("/latency")
async def get_latency_metrics():
    """Observability dashboard endpoint returning stage latency metrics."""
    from app.routes.brain import brain_service
    from app.routes.voice import voice_service

    return {
        "stt_latency_ms": round(voice_service.last_stt_latency * 1000, 2),
        "tts_latency_ms": round(voice_service.last_tts_latency * 1000, 2),
        "last_llm_first_token_ms": round(getattr(brain_service, "last_first_token_latency", 0.0) * 1000, 2),
        "last_tool_execution_ms": round(getattr(brain_service, "last_tool_latency", 0.0) * 1000, 2),
        "last_memory_lookup_ms": round(getattr(brain_service, "last_memory_latency", 0.0) * 1000, 2),
        "total_pipeline_ms": round(
            (
                voice_service.last_stt_latency
                + voice_service.last_tts_latency
                + getattr(brain_service, "last_first_token_latency", 0.0)
            ) * 1000,
            2,
        ),
    }


class SettingsUpdateRequest(BaseModel):
    ai_provider: str | None = None
    gemini_api_key: str | None = None
    gemini_model: str | None = None
    openai_api_key: str | None = None
    elevenlabs_api_key: str | None = None


@router.get("/settings")
async def get_settings():
    """Get active system & AI provider settings."""
    from config.settings import settings

    return {
        "ai_provider": settings.ai_provider,
        "gemini_model": settings.gemini_model,
        "gemini_api_key_configured": bool(settings.gemini_api_key),
        "gemini_api_key_masked": f"...{settings.gemini_api_key[-4:]}" if len(settings.gemini_api_key) >= 4 else "",
        "openai_model": settings.openai_model,
        "openai_api_key_configured": bool(settings.openai_api_key),
        "elevenlabs_api_key_configured": bool(settings.elevenlabs_api_key),
    }


@router.post("/settings")
async def update_settings(request: SettingsUpdateRequest):
    """Update runtime AI provider settings, persist to .env, and re-instantiate provider."""
    import re
    from pathlib import Path

    from app.providers.factory import build_provider
    from app.routes.brain import brain_service
    from config.settings import settings

    if request.ai_provider is not None:
        settings.ai_provider = request.ai_provider.strip().lower()
    if request.gemini_api_key is not None:
        settings.gemini_api_key = request.gemini_api_key.strip()
    if request.gemini_model is not None:
        settings.gemini_model = request.gemini_model.strip()
    if request.openai_api_key is not None:
        settings.openai_api_key = request.openai_api_key.strip()
    if request.elevenlabs_api_key is not None:
        settings.elevenlabs_api_key = request.elevenlabs_api_key.strip()

    # Dynamic provider re-binding
    brain_service.provider = build_provider(settings)
    logger.info("Re-bound BrainService provider to %s (%s)", brain_service.provider.name, brain_service.provider.model)

    # Persist to local .env file if present
    env_path = Path(".env")
    if env_path.is_file():
        try:
            content = env_path.read_text(encoding="utf-8")
            updates = {
                "AI_PROVIDER": settings.ai_provider,
                "GEMINI_API_KEY": settings.gemini_api_key,
                "GEMINI_MODEL": settings.gemini_model,
            }
            for k, v in updates.items():
                pattern = re.compile(rf"^{k}=.*$", re.MULTILINE)
                if pattern.search(content):
                    content = pattern.sub(f"{k}={v}", content)
                else:
                    content += f"\n{k}={v}"
            env_path.write_text(content, encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not persist settings to .env: %s", exc)

    return {
        "status": "updated",
        "ai_provider": settings.ai_provider,
        "gemini_model": settings.gemini_model,
        "gemini_api_key_configured": bool(settings.gemini_api_key),
    }

