import asyncio
import logging
import platform
from typing import ClassVar

import psutil

from app.tools.base import PermissionLevel, Tool, ToolResult
from app.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


@ToolRegistry.register
class SystemTool(Tool):
    name = "system"
    description = "Returns system information: CPU usage and model, RAM, disk, OS, hostname, battery"
    parameters: ClassVar[dict] = {}
    output_schema: ClassVar[dict] = {
        "type": "object",
        "properties": {
            "cpu_usage_percent": {"type": "number"},
            "cpu_model": {"type": "string"},
            "total_ram_gb": {"type": "number"},
            "used_ram_gb": {"type": "number"},
            "free_ram_gb": {"type": "number"},
            "os": {"type": "string"},
            "hostname": {"type": "string"},
        },
    }
    permission_level = PermissionLevel.READ_ONLY
    timeout = 5.0

    _cpu_warmed: ClassVar[bool] = False

    async def execute(self, **kwargs) -> ToolResult:
        if not SystemTool._cpu_warmed:
            SystemTool._cpu_warmed = True
            cpu_usage = await asyncio.to_thread(psutil.cpu_percent, 0.1)
        else:
            cpu_usage = psutil.cpu_percent(None)
        cpu_model = platform.processor() or platform.machine()

        mem = psutil.virtual_memory()
        disk = psutil.disk_usage("/")

        os_name = f"{platform.system()} {platform.release()}"
        hostname = platform.node()

        try:
            battery = psutil.sensors_battery()
        except Exception as e:
            logger.debug("Battery sensor unavailable: %s", e)
            battery = None
        battery_percent = round(battery.percent, 1) if battery else None

        return ToolResult(
            success=True,
            data={
                "cpu_usage_percent": cpu_usage,
                "cpu_model": cpu_model,
                "total_ram_gb": round(mem.total / (1024**3), 2),
                "used_ram_gb": round(mem.used / (1024**3), 2),
                "free_ram_gb": round(mem.available / (1024**3), 2),
                "disk_usage_gb": {
                    "total": round(disk.total / (1024**3), 2),
                    "used": round(disk.used / (1024**3), 2),
                    "free": round(disk.free / (1024**3), 2),
                },
                "os": os_name,
                "hostname": hostname,
                "battery_percent": battery_percent,
            },
        )
