"""App Launcher & Computer Control Tool for FALSO Personal AI Companion.

Allows FALSO to open applications (Chrome, Explorer, VS Code), close processes,
and open web URLs cleanly on Windows.
"""

from __future__ import annotations

import logging
import os
import re
import subprocess
import webbrowser
from typing import Any, Dict

import psutil

from app.tools.base import Tool, ToolResult
from app.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)

_LAUNCHABLE = (
    "vs code", "vscode", "visual studio code",
    "chrome", "google chrome",
    "notepad", "explorer", "file explorer",
    "terminal", "powershell", "cmd", "command prompt",
    "firefox", "edge", "word", "excel", "calculator", "calc", "paint",
)


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

    @classmethod
    def match_prompt(cls, prompt: str, context: Any = None) -> dict | None:
        """Strict matcher: only literal app-launch phrases, so this tool never
        hijacks file reads/searches that merely contain the word 'open'."""
        prompt_lower = prompt.lower().strip()
        m = re.search(
            r'\b(?:open|launch|start|run)\s+(?:the\s+)?(' + r"|".join(map(re.escape, _LAUNCHABLE)) + r')',
            prompt_lower,
        )
        if not m:
            return None
        return {"action": "open_app", "target": m.group(1).strip()}

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
                "google chrome": "chrome.exe",
                "explorer": "explorer.exe",
                "file explorer": "explorer.exe",
                "code": "code",
                "vs code": "code",
                "vscode": "code",
                "visual studio code": "code",
                "notepad": "notepad.exe",
                "terminal": "powershell.exe",
                "powershell": "powershell.exe",
                "cmd": "cmd.exe",
                "command prompt": "cmd.exe",
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
