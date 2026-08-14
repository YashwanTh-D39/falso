from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from app.tools.base import PermissionLevel, ToolResult
from app.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)

# Maximum wall-clock time for a single tool execution.
TOOL_EXECUTION_TIMEOUT = 30.0


class ToolManager:
    def __init__(self, registry: ToolRegistry | None = None) -> None:
        self.registry = registry or ToolRegistry

    async def execute(self, name: str, **kwargs: Any) -> ToolResult:
        from app.services.automation.permissions import permission_manager

        if permission_manager.is_lockdown_active():
            logger.warning("[PERMISSIONS] Tool execution blocked by Emergency Lockdown | tool=%s", name)
            return ToolResult(
                success=False,
                error="FALSO Emergency Lockdown Active: Tool execution disabled.",
            )

        tool_cls = self.registry.get(name)
        if tool_cls is None:
            logger.error("Unknown tool requested: '%s'", name)
            return ToolResult(
                success=False,
                error=f"Unknown tool: '{name}'",
            )

        # Check central PermissionManager capability & confirmation rules
        perm_check = permission_manager.check_capability(f"tool.{name}", target=str(kwargs))
        if not perm_check.allowed:
            logger.warning("[PERMISSIONS] Access DENIED for tool '%s': %s", name, perm_check.reason)
            return ToolResult(
                success=False,
                error=perm_check.reason,
            )

        tool = tool_cls()
        perm_level = getattr(tool, "permission_level", PermissionLevel.READ_ONLY)
        perm_str = perm_level.value if isinstance(perm_level, PermissionLevel) else str(perm_level)

        # Confirmation enforcement for non-READ_ONLY tools or high-impact actions
        if (perm_check.requires_confirmation or perm_str in ("low_risk", "destructive")) and not kwargs.get("confirmed", False):
            logger.warning("Tool '%s' requires confirmation (permission_level=%s)", name, perm_str)
            return ToolResult(
                success=False,
                data={
                    "confirmation_required": True,
                    "permission_level": perm_str,
                    "tool": name,
                    "args": kwargs,
                },
                error=f"Confirmation required for {perm_str} tool '{name}'",
            )

        tool_timeout = float(getattr(tool, "timeout", TOOL_EXECUTION_TIMEOUT))
        logger.info("Executing tool '%s' with parameters: %s (timeout=%.1fs)", name, kwargs, tool_timeout)
        start = time.perf_counter()

        try:
            result = await asyncio.wait_for(
                tool.execute(**kwargs),
                timeout=tool_timeout,
            )
            elapsed = time.perf_counter() - start
            result.execution_time = elapsed

            res_status = "SUCCESS" if result.success else "FAILED"
            permission_manager.log_action(
                task_id=kwargs.get("task_id", "FALSO-TASK"),
                request_id=kwargs.get("request_id", "REQ-001"),
                action_id=name,
                capability=f"tool.{name}",
                target=str(kwargs),
                result=res_status,
                duration_ms=elapsed * 1000.0,
            )

            if result.success:
                logger.info("Tool '%s' succeeded in %.3fs", name, elapsed)
            else:
                logger.warning("Tool '%s' failed in %.3fs: %s", name, elapsed, result.error)

            return result

        except (TimeoutError, asyncio.TimeoutError):
            elapsed = time.perf_counter() - start
            logger.warning("Tool '%s' timed out after %.3fs (limit=%.1fs)", name, elapsed, tool_timeout)
            return ToolResult(
                success=False,
                error=f"Tool '{name}' timed out after {tool_timeout:.0f}s",
                execution_time=elapsed,
            )

        except Exception as e:
            elapsed = time.perf_counter() - start
            logger.exception("Tool '%s' raised an exception after %.3fs", name, elapsed)
            return ToolResult(
                success=False,
                error=str(e),
                execution_time=elapsed,
            )
