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
