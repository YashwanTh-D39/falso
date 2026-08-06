"""App Launcher & Computer Control Tool for FALSO Personal AI Companion.

Allows FALSO to open applications (Chrome, Explorer, VS Code), close processes,
and open web URLs cleanly on Windows.
"""

from __future__ import annotations

import logging
import os
import subprocess
import webbrowser
from typing import Any, Dict

import psutil

from app.tools.base import Tool, ToolResult
from app.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


@ToolRegistry.register
class AppLauncherTool(Tool):
    name = "app_launcher"
    description = "Launches applications (Chrome, Explorer, VS Code), closes processes, or opens web URLs."
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["open_app", "close_app", "open_url"],
                "description": "Action to perform"
            },
            "target": {
                "type": "string",
                "description": "Application name, executable (e.g., 'chrome', 'explorer', 'code'), or URL"
            }
        },
        "required": ["action", "target"]
    }

    async def execute(self, action: str, target: str, **kwargs: Any) -> ToolResult:
        target_clean = target.strip()
        
        if action == "open_url":
            if not target_clean.startswith(("http://", "https://")):
                target_clean = "https://" + target_clean
            webbrowser.open(target_clean)
            return ToolResult(
                success=True,
                data={"url": target_clean},
                error=None
            )

        elif action == "open_app":
            app_map = {
                "chrome": "chrome.exe",
                "explorer": "explorer.exe",
                "code": "code",
                "vscode": "code",
                "notepad": "notepad.exe",
                "terminal": "powershell.exe"
            }
            exe = app_map.get(target_clean.lower(), target_clean)
            try:
                subprocess.Popen(exe, shell=True)
                return ToolResult(
                    success=True,
                    data={"app": target_clean, "exe": exe},
                    error=None
                )
            except Exception as exc:
                return ToolResult(
                    success=False,
                    data=None,
                    error=f"Failed to launch app '{target_clean}': {exc}"
                )

        elif action == "close_app":
            closed_count = 0
            target_lower = target_clean.lower()
            for p in psutil.process_iter(['pid', 'name']):
                try:
                    if p.info['name'] and target_lower in p.info['name'].lower():
                        p.terminate()
                        closed_count += 1
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            return ToolResult(
                success=True,
                data={"app": target_clean, "closed_processes": closed_count},
                error=None
            )

        return ToolResult(
            success=False,
            data=None,
            error=f"Unsupported action '{action}'"
        )
