from datetime import datetime
from typing import ClassVar

from app.tools.base import PermissionLevel, Tool, ToolResult
from app.tools.registry import ToolRegistry


@ToolRegistry.register
class TimeTool(Tool):
    name = "time"
    description = "Returns the current local time, date, and timezone"
    parameters: ClassVar[dict] = {}
    output_schema: ClassVar[dict] = {
        "type": "object",
        "properties": {
            "time": {"type": "string"},
            "date": {"type": "string"},
            "timezone": {"type": "string"},
        },
    }
    permission_level = PermissionLevel.READ_ONLY
    timeout = 3.0

    async def execute(self, **kwargs) -> ToolResult:
        now = datetime.now().astimezone()
        return ToolResult(
            success=True,
            data={
                "time": now.strftime("%H:%M:%S"),
                "date": now.strftime("%Y-%m-%d"),
                "timezone": now.tzname() or "UTC",
            },
        )
