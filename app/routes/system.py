import logging
import os
import re
from pathlib import Path

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
    elevenlabs_voice_id: str | None = None
    tts_provider: str | None = None


@router.get("/settings")
async def get_settings():
    """Get active system & AI provider & voice settings."""
    from config.settings import settings

    el_key_valid = bool(settings.elevenlabs_api_key and not is_placeholder_key(settings.elevenlabs_api_key))
    el_masked = f"...{settings.elevenlabs_api_key[-4:]}" if len(settings.elevenlabs_api_key) >= 4 else ""

    gem_key_valid = bool(settings.gemini_api_key and not is_placeholder_key(settings.gemini_api_key))
    gem_masked = f"...{settings.gemini_api_key[-4:]}" if len(settings.gemini_api_key) >= 4 else ""

    return {
        "ai_provider": settings.ai_provider,
        "ollama_model": settings.ollama_model,
        "ollama_base_url": settings.ollama_base_url,
        "gemini_model": settings.gemini_model,
        "gemini_api_key_configured": gem_key_valid,
        "gemini_api_key_masked": gem_masked,
        "openai_model": settings.openai_model,
        "openai_api_key_configured": bool(settings.openai_api_key and not is_placeholder_key(settings.openai_api_key)),
        "elevenlabs_api_key_configured": el_key_valid,
        "elevenlabs_api_key_masked": el_masked,
        "elevenlabs_voice_id": settings.elevenlabs_voice_id,
        "tts_provider": settings.tts_provider,
    }


INVALID_PLACEHOLDER_KEYS = {
    "test_key",
    "test_key_12345",
    "dummy",
    "example",
    "changeme",
    "your_api_key",
    "your_gemini_api_key",
    "your_elevenlabs_api_key",
    "placeholder",
}


def is_placeholder_key(key: str | None) -> bool:
    if not key:
        return False
    k = key.strip().lower()
    if k in INVALID_PLACEHOLDER_KEYS:
        return True
    return any(k.startswith(prefix) for prefix in ("test_key", "dummy", "example", "changeme", "your_"))


def persist_settings_to_env(target_settings, target_path: Path = Path(".env")) -> bool:
    """Persist active settings to .env file, skipping when under test environment or targeting placeholder keys."""
    is_testing = os.getenv("FALSO_TESTING") == "1" or "PYTEST_CURRENT_TEST" in os.environ
    real_env_target = target_path.resolve() == Path(".env").resolve()

    if is_testing and real_env_target:
        logger.info("[TEST ISOLATION] Skipping real .env persistence during test execution.")
        return False

    if not target_path.is_file():
        return False

    try:
        content = target_path.read_text(encoding="utf-8")
        gemini_key_to_write = target_settings.gemini_api_key if not is_placeholder_key(target_settings.gemini_api_key) else ""
        el_key_to_write = target_settings.elevenlabs_api_key if not is_placeholder_key(target_settings.elevenlabs_api_key) else ""

        updates = {
            "AI_PROVIDER": target_settings.ai_provider,
            "GEMINI_API_KEY": gemini_key_to_write,
            "GEMINI_MODEL": target_settings.gemini_model,
            "ELEVENLABS_API_KEY": el_key_to_write,
            "ELEVENLABS_VOICE_ID": target_settings.elevenlabs_voice_id,
            "TTS_PROVIDER": target_settings.tts_provider,
        }
        for k, v in updates.items():
            pattern = re.compile(rf"^{k}=.*$", re.MULTILINE)
            if pattern.search(content):
                content = pattern.sub(f"{k}={v}", content)
            else:
                content += f"\n{k}={v}"
        target_path.write_text(content, encoding="utf-8")
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not persist settings to %s: %s", target_path, exc)
        return False


@router.post("/settings")
async def update_settings(request: SettingsUpdateRequest):
    """Update runtime AI provider & voice settings, persist to .env (outside tests), and re-instantiate engines."""
    from app.providers.factory import build_provider
    from app.routes.brain import brain_service
    from app.routes.voice import voice_service
    from config.settings import settings
    from voice.elevenlabs import ElevenLabsTTSEngine
    from voice.tts import LocalTTSEngine

    if request.ai_provider is not None:
        settings.ai_provider = request.ai_provider.strip().lower()
    if request.gemini_api_key is not None:
        key_candidate = request.gemini_api_key.strip()
        if is_placeholder_key(key_candidate):
            logger.warning("Rejected placeholder GEMINI_API_KEY from persistence: %s", key_candidate)
        else:
            settings.gemini_api_key = key_candidate
    if request.gemini_model is not None:
        settings.gemini_model = request.gemini_model.strip()
    if request.openai_api_key is not None:
        settings.openai_api_key = request.openai_api_key.strip()

    # ElevenLabs & Voice settings
    if request.elevenlabs_api_key is not None:
        el_candidate = request.elevenlabs_api_key.strip()
        if is_placeholder_key(el_candidate):
            logger.warning("Rejected placeholder ELEVENLABS_API_KEY from persistence: %s", el_candidate)
        else:
            settings.elevenlabs_api_key = el_candidate
    if request.elevenlabs_voice_id is not None:
        settings.elevenlabs_voice_id = request.elevenlabs_voice_id.strip()
    if request.tts_provider is not None:
        settings.tts_provider = request.tts_provider.strip().lower()

    # Dynamic AI provider re-binding
    brain_service.provider = build_provider(settings)
    logger.info("Re-bound BrainService provider to %s (%s)", brain_service.provider.name, brain_service.provider.model)

    # Dynamic TTS engine re-binding
    if settings.tts_provider == "elevenlabs" and settings.elevenlabs_api_key and not is_placeholder_key(settings.elevenlabs_api_key):
        voice_service.tts_engine = ElevenLabsTTSEngine(
            api_key=settings.elevenlabs_api_key,
            voice_id=settings.elevenlabs_voice_id,
        )
        logger.info("Re-bound VoiceService TTS engine to ElevenLabs (voice_id=%s)", settings.elevenlabs_voice_id)
    else:
        voice_service.tts_engine = LocalTTSEngine()
        logger.info("Re-bound VoiceService TTS engine to LocalTTSEngine")

    # Persist settings using helper
    persist_settings_to_env(settings)

    el_configured = bool(settings.elevenlabs_api_key and not is_placeholder_key(settings.elevenlabs_api_key))

    return {
        "status": "updated",
        "ai_provider": settings.ai_provider,
        "gemini_model": settings.gemini_model,
        "gemini_api_key_configured": bool(settings.gemini_api_key and not is_placeholder_key(settings.gemini_api_key)),
        "elevenlabs_api_key_configured": el_configured,
        "elevenlabs_voice_id": settings.elevenlabs_voice_id,
        "tts_provider": settings.tts_provider,
    }


@router.get("/voices")
async def get_elevenlabs_voices():
    """Fetch available ElevenLabs voices dynamically via ElevenLabs API."""
    import httpx

    from config.settings import settings

    key = settings.elevenlabs_api_key
    default_voices = [
        {"voice_id": "21m00Tcm4TlvDq8ikWAM", "name": "Rachel (Default / Female)"},
        {"voice_id": "AZnzlk1XvdvUeBnXmlld", "name": "Domi (Female)"},
        {"voice_id": "EXAVITQu4vr4xnSDxMaL", "name": "Bella (Female)"},
        {"voice_id": "ErXwobaYiN019PkySvjV", "name": "Antoni (Male)"},
        {"voice_id": "MF3mGyEYCl7XYWbV9V6O", "name": "Elli (Female)"},
        {"voice_id": "TxGEqnHWrfWFTfGW9XjX", "name": "Josh (Male)"},
        {"voice_id": "VR6AewLTigWG4xTvo155", "name": "Arnold (Male)"},
        {"voice_id": "pNInz6obpgDQGcFmaJgB", "name": "Adam (Male)"},
        {"voice_id": "yoZ06aGfM25m30UU3Cgh", "name": "Sam (Male)"},
    ]

    if not key or is_placeholder_key(key):
        logger.info("ElevenLabs key unconfigured or placeholder — returning default voices")
        return {"voices": default_voices}

    try:
        url = "https://api.elevenlabs.io/v1/voices"
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, headers={"xi-api-key": key})
            if resp.status_code == 200:
                data = resp.json()
                raw_voices = data.get("voices", [])
                formatted = [
                    {
                        "voice_id": v.get("voice_id"),
                        "name": f"{v.get('name')} ({v.get('category', 'custom').title()})",
                    }
                    for v in raw_voices
                    if v.get("voice_id") and v.get("name")
                ]
                if formatted:
                    logger.info("Voice list fetched successfully from ElevenLabs (%d voices found)", len(formatted))
                    return {"voices": formatted}
            else:
                logger.warning("ElevenLabs voices API status=%d: %s", resp.status_code, resp.text[:100])
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not fetch ElevenLabs voices: %s", exc)

    return {"voices": default_voices}


@router.get("/models")
async def discover_models():
    """Discover available Gemini models dynamically via Google AI Studio API."""
    import httpx

    from config.settings import settings

    key = settings.gemini_api_key
    if not key:
        return {"models": ["gemini-3.6-flash", "gemini-3.1-flash", "gemini-3.1-pro", "gemini-1.5-flash", "gemini-1.5-pro"]}

    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models?key={key}"
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url)
            if resp.status_code == 200:
                data = resp.json()
                raw_models = data.get("models", [])
                names = []
                for m in raw_models:
                    name = m.get("name", "").replace("models/", "")
                    if "gemini" in name and "generateContent" in m.get("supportedGenerationMethods", []):
                        names.append(name)
                if names:
                    return {"models": names}
    except Exception as exc:  # noqa: BLE001
        logger.debug("Could not query Gemini models endpoint: %s", exc)

    return {"models": ["gemini-3.6-flash", "gemini-3.1-flash", "gemini-3.1-pro", "gemini-1.5-flash", "gemini-1.5-pro"]}


@router.post("/test-connection")
async def test_connection():
    """Test connection to active AI provider."""
    import httpx

    from config.settings import settings

    if settings.ai_provider == "ollama":
        try:
            url = f"{settings.ollama_base_url.rstrip('/')}/api/tags"
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    return {"status": "ok", "message": f"Successfully connected to Ollama ({settings.ollama_model})"}
                return {"status": "error", "message": "Local model unavailable."}
        except Exception:  # noqa: BLE001
            return {"status": "error", "message": "Local model unavailable."}

    key = settings.gemini_api_key
    if not key:
        return {"status": "error", "message": "Gemini API key is missing. Set GEMINI_API_KEY in .env"}

    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{settings.gemini_model}?key={key}"
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url)
            if resp.status_code == 200:
                return {"status": "ok", "message": f"Successfully connected to Gemini API ({settings.gemini_model})"}
            return {"status": "error", "message": f"Gemini API returned status {resp.status_code}"}
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "message": f"Connection failed: {exc}"}

