import logging

from fastapi import APIRouter

import app.tools.time_tool  # noqa: F401 — trigger ToolRegistry registration
from app.tools.manager import ToolManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/tools", tags=["Tools"])
manager = ToolManager()


@router.get("/time")
async def get_time():
    result = await manager.execute("time")
    return result.data
