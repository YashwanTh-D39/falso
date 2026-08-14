"""Read-only Computer Awareness Tools for FALSO Agentic Architecture.

Includes:
- CpuRamTool (cpu_ram)
- RunningAppsTool (running_apps)
- ActiveWindowTool (active_window)
- CurrentProjectTool (current_project)
- NetworkStatusTool (network_status)
"""

from __future__ import annotations

import logging
from typing import ClassVar, Dict, Any

from app.services.context_detector import context_detector
from app.tools.base import PermissionLevel, Tool, ToolResult
from app.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


@ToolRegistry.register
class CpuRamTool(Tool):
    name = "cpu_ram"
    description = "Returns real-time CPU usage percentage and memory stats"
    parameters: ClassVar[dict] = {}
    output_schema: ClassVar[dict] = {
        "type": "object",
        "properties": {
            "cpu_usage": {"type": "string"},
            "ram_usage": {"type": "string"},
        },
    }
    permission_level = PermissionLevel.READ_ONLY
    timeout = 3.0

    async def execute(self, **kwargs: Any) -> ToolResult:
        try:
            ctx = context_detector.detect_context()
            return ToolResult(
                success=True,
                data={
                    "cpu_usage": ctx["cpu_usage"],
                    "ram_usage": ctx["ram_usage"],
                },
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e))


@ToolRegistry.register
class RunningAppsTool(Tool):
    name = "running_apps"
    description = "Returns list of active running applications"
    parameters: ClassVar[dict] = {}
    output_schema: ClassVar[dict] = {
        "type": "object",
        "properties": {
            "running_apps": {"type": "array", "items": {"type": "string"}},
        },
    }
    permission_level = PermissionLevel.READ_ONLY
    timeout = 3.0

    async def execute(self, **kwargs: Any) -> ToolResult:
        try:
            ctx = context_detector.detect_context()
            return ToolResult(
                success=True,
                data={
                    "running_apps": ctx["running_apps"],
                },
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e))


@ToolRegistry.register
class ActiveWindowTool(Tool):
    name = "active_window"
    description = "Returns current foreground window title and active application"
    parameters: ClassVar[dict] = {}
    output_schema: ClassVar[dict] = {
        "type": "object",
        "properties": {
            "active_app": {"type": "string"},
            "active_window": {"type": "string"},
        },
    }
    permission_level = PermissionLevel.READ_ONLY
    timeout = 3.0

    async def execute(self, **kwargs: Any) -> ToolResult:
        try:
            ctx = context_detector.detect_context()
            return ToolResult(
                success=True,
                data={
                    "active_app": ctx["active_app"],
                    "active_window": ctx["active_window"],
                },
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e))


@ToolRegistry.register
class CurrentProjectTool(Tool):
    name = "current_project"
    description = "Returns current open project workspace and Git status"
    parameters: ClassVar[dict] = {}
    output_schema: ClassVar[dict] = {
        "type": "object",
        "properties": {
            "current_project": {"type": "string"},
            "current_workspace": {"type": "string"},
            "git_branch": {"type": "string"},
        },
    }
    permission_level = PermissionLevel.READ_ONLY
    timeout = 3.0

    async def execute(self, **kwargs: Any) -> ToolResult:
        try:
            ctx = context_detector.detect_context()
            return ToolResult(
                success=True,
                data={
                    "current_project": ctx["current_project"],
                    "current_workspace": ctx["current_workspace"],
                    "git_branch": ctx["git_branch"],
                },
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e))


@ToolRegistry.register
class NetworkStatusTool(Tool):
    name = "network_status"
    description = "Returns network connectivity status"
    parameters: ClassVar[dict] = {}
    output_schema: ClassVar[dict] = {
        "type": "object",
        "properties": {
            "network_status": {"type": "string"},
        },
    }
    permission_level = PermissionLevel.READ_ONLY
    timeout = 3.0

    async def execute(self, **kwargs: Any) -> ToolResult:
        try:
            ctx = context_detector.detect_context()
            return ToolResult(
                success=True,
                data={
                    "network_status": ctx["network_status"],
                },
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e))
