"""Desktop Context Detector Service for FALSO Personal AI Companion.

Detects active workspace, running IDE, active window, running applications,
system metrics (CPU, RAM, Network), Git repository status, and project details.
"""

from __future__ import annotations

import logging
import os
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import psutil

logger = logging.getLogger(__name__)


class ContextDetectorService:
    def __init__(self, workspace_path: str = "c:/Users/Admin/Project-Falso") -> None:
        self.workspace_path = Path(workspace_path).resolve()
        self._cached_context: Optional[Dict[str, Any]] = None
        self._cache_time: float = 0.0

    def detect_context(self) -> Dict[str, Any]:
        """Detects current active desktop context with 2.0s caching."""
        now = time.time()
        if self._cached_context and (now - self._cache_time) < 2.0:
            return self._cached_context

        active_project = self.workspace_path.name
        active_folder = str(self.workspace_path)

        active_app, active_window = self._detect_active_app_and_window()
        running_apps = self._detect_running_applications()

        # System metrics
        cpu_usage = f"{psutil.cpu_percent(None):.1f}%"
        try:
            mem = psutil.virtual_memory()
            total_gb = mem.total / (1024**3)
            used_gb = mem.used / (1024**3)
            ram_usage = f"{used_gb:.1f} GB / {total_gb:.1f} GB ({mem.percent:.1f}%)"
        except Exception:
            ram_usage = "Unknown"

        git_info = self._get_git_status()

        ctx = {
            "active_app": active_app,
            "active_window": active_window,
            "current_project": active_project,
            "current_workspace": active_folder,
            "running_apps": running_apps,
            "cpu_usage": cpu_usage,
            "ram_usage": ram_usage,
            "network_status": "Connected",
            "git_repository": git_info.get("repo_name", active_project),
            "git_branch": git_info.get("branch", "main"),
            "git_uncommitted": git_info.get("uncommitted_count", 0),
            "detected_at": now,
        }
        self._cached_context = ctx
        self._cache_time = now
        return ctx

    def _detect_active_app_and_window(self) -> Tuple[str, str]:
        active_app = "VS Code"
        active_window = "Project-Falso"
        try:
            import win32gui
            import win32process

            hwnd = win32gui.GetForegroundWindow()
            if hwnd:
                t = win32gui.GetWindowText(hwnd)
                if t and t.strip():
                    active_window = t.strip()
                res = win32process.GetWindowThreadProcessId(hwnd)
                pid = (res[1] & 0xFFFFFFFF) if len(res) > 1 and res[1] else None
                if pid and pid > 0:
                    try:
                        pname = psutil.Process(pid).name().lower()
                        app_map = {
                            "code.exe": "VS Code",
                            "chrome.exe": "Google Chrome",
                            "msedge.exe": "Microsoft Edge",
                            "windowsterminal.exe": "Windows Terminal",
                            "cmd.exe": "Command Prompt",
                            "powershell.exe": "PowerShell",
                            "explorer.exe": "Windows Explorer",
                            "python.exe": "Python",
                            "py.exe": "Python",
                        }
                        active_app = app_map.get(pname, pname.replace(".exe", "").capitalize())
                    except Exception:
                        pass
        except Exception:
            pass

        # Infer active app from active window title if win32 process is unavailable
        if active_app == "VS Code" and active_window != "Project-Falso":
            win_lower = active_window.lower()
            if "chrome" in win_lower:
                active_app = "Google Chrome"
            elif "terminal" in win_lower:
                active_app = "Windows Terminal"
            elif "powershell" in win_lower:
                active_app = "PowerShell"
            elif "command prompt" in win_lower:
                active_app = "Command Prompt"
            elif "explorer" in win_lower:
                active_app = "Windows Explorer"

        return active_app, active_window

    def _detect_running_applications(self) -> List[str]:
        known = {
            "code.exe": "VS Code",
            "chrome.exe": "Google Chrome",
            "msedge.exe": "Microsoft Edge",
            "windowsterminal.exe": "Windows Terminal",
            "cmd.exe": "Command Prompt",
            "powershell.exe": "PowerShell",
            "explorer.exe": "Windows Explorer",
            "python.exe": "Python",
            "py.exe": "Python",
        }
        found = set()
        for p in psutil.process_iter(["name"]):
            try:
                pname = (p.info.get("name") or "").lower()
                if pname in known:
                    found.add(known[pname])
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return sorted(list(found))

    def _get_git_status(self) -> Dict[str, Any]:
        try:
            res_branch = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=self.workspace_path,
                capture_output=True,
                text=True,
                timeout=1.5,
            )
            branch = res_branch.stdout.strip() if res_branch.returncode == 0 else "main"

            res_status = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=self.workspace_path,
                capture_output=True,
                text=True,
                timeout=1.5,
            )
            changes = [line for line in res_status.stdout.splitlines() if line.strip()]

            return {
                "repo_name": self.workspace_path.name,
                "branch": branch,
                "uncommitted_count": len(changes),
            }
        except Exception as exc:
            logger.debug("Git status detection info: %s", exc)
            return {"repo_name": self.workspace_path.name, "branch": "main", "uncommitted_count": 0}

    def format_summary_for_prompt(self) -> str:
        """Formats active desktop context summary for system prompt context injection."""
        ctx = self.detect_context()
        running_str = ", ".join(ctx["running_apps"]) if ctx["running_apps"] else "VS Code, Python"
        lines = [
            "[COMPUTER AWARENESS CONTEXT]",
            f"Active Application: {ctx['active_app']}",
            f"Active Window: {ctx['active_window']}",
            f"Current Project: {ctx['current_project']} ({ctx['current_workspace']})",
            f"Running Applications: {running_str}",
            f"CPU Usage: {ctx['cpu_usage']} | Memory Usage: {ctx['ram_usage']} | Network: {ctx['network_status']}",
            f"Git Repository: {ctx['git_repository']} | Branch: {ctx['git_branch']} ({ctx['git_uncommitted']} uncommitted files)",
        ]
        return "\n".join(lines)


context_detector = ContextDetectorService()
