from datetime import datetime

from app.tools.base import Tool, ToolResult
from app.tools.registry import ToolRegistry


@ToolRegistry.register
class TimeTool(Tool):
    name = "time"
    description = "Returns the current local time, date, and timezone"
    parameters = {}

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
