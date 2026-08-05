import logging

from fastapi import APIRouter

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

