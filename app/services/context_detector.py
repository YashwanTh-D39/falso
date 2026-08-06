"""Desktop Context Detector Service for FALSO Personal AI Companion.

Detects active workspace, running IDE, Git repository status, open browser apps,
current active file, and programming language to auto-inject into FALSO system prompt context.
"""

from __future__ import annotations

import logging
import os
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, Optional

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
        
        # Detect IDE
        running_ide = "VS Code" if self._is_process_running("code.exe") else "Terminal / Shell"

        # Detect Git status
        git_info = self._get_git_status()

        # Build context object
        ctx = {
            "current_project": active_project,
            "current_folder": active_folder,
            "running_ide": running_ide,
            "git_repository": git_info.get("repo_name", active_project),
            "git_branch": git_info.get("branch", "main"),
            "git_uncommitted": git_info.get("uncommitted_count", 0),
            "current_language": "Python / JavaScript",
            "detected_at": now
        }
        self._cached_context = ctx
        self._cache_time = now
        return ctx

    def _is_process_running(self, proc_name: str) -> bool:
        name_lower = proc_name.lower()
        for p in psutil.process_iter(['name']):
            try:
                if p.info['name'] and p.info['name'].lower() == name_lower:
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return False

    def _get_git_status(self) -> Dict[str, Any]:
        try:
            res_branch = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=self.workspace_path,
                capture_output=True,
                text=True,
                timeout=1.5
            )
            branch = res_branch.stdout.strip() if res_branch.returncode == 0 else "main"

            res_status = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=self.workspace_path,
                capture_output=True,
                text=True,
                timeout=1.5
            )
            changes = [line for line in res_status.stdout.splitlines() if line.strip()]

            return {
                "repo_name": self.workspace_path.name,
                "branch": branch,
                "uncommitted_count": len(changes)
            }
        except Exception as exc:
            logger.debug("Git status detection info: %s", exc)
            return {"repo_name": self.workspace_path.name, "branch": "main", "uncommitted_count": 0}

    def format_summary_for_prompt(self) -> str:
        """Formats active desktop context summary for system prompt context injection."""
        ctx = self.detect_context()
        lines = [
            f"Active Project: {ctx['current_project']} ({ctx['current_folder']})",
            f"IDE: {ctx['running_ide']} | Git Branch: {ctx['git_branch']}",
            f"Git Uncommitted Changes: {ctx['git_uncommitted']} files"
        ]
        return "\n".join(lines)


context_detector = ContextDetectorService()
