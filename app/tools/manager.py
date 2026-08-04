from __future__ import annotations

import logging
import time
from typing import Any

from app.tools.base import ToolResult
from app.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


class ToolManager:
    def __init__(self, registry: ToolRegistry | None = None) -> None:
        self.registry = registry or ToolRegistry

    async def execute(self, name: str, **kwargs: Any) -> ToolResult:
        tool_cls = self.registry.get(name)
        if tool_cls is None:
            logger.error("Unknown tool requested: '%s'", name)
            return ToolResult(
                success=False,
                error=f"Unknown tool: '{name}'",
            )

        tool = tool_cls()
        logger.info(
            "Executing tool '%s' with parameters: %s",
            name,
            kwargs,
        )
        start = time.perf_counter()

        try:
            result = await tool.execute(**kwargs)
            elapsed = time.perf_counter() - start
            result.execution_time = elapsed

            if result.success:
                logger.info(
                    "Tool '%s' succeeded in %.3fs",
                    name,
                    elapsed,
                )
            else:
                logger.warning(
                    "Tool '%s' failed in %.3fs: %s",
                    name,
                    elapsed,
                    result.error,
                )

            return result

        except Exception as e:
            elapsed = time.perf_counter() - start
            logger.exception(
                "Tool '%s' raised an exception after %.3fs",
                name,
                elapsed,
            )
            return ToolResult(
                success=False,
                error=str(e),
                execution_time=elapsed,
            )
