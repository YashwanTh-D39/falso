import asyncio
import platform

import psutil

from app.tools.base import Tool, ToolResult
from app.tools.registry import ToolRegistry


@ToolRegistry.register
class SystemTool(Tool):
    name = "system"
    description = "Returns system information: CPU usage and model, RAM, disk, OS, hostname, battery"
    parameters = {}

    async def execute(self, **kwargs) -> ToolResult:
        cpu_usage = await asyncio.to_thread(psutil.cpu_percent, 0.5)
        cpu_model = platform.processor() or platform.machine()

        mem = psutil.virtual_memory()

        disk = psutil.disk_usage("/")

        os_name = f"{platform.system()} {platform.release()}"
        hostname = platform.node()

        battery = psutil.sensors_battery()
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
