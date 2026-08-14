"""Workspace Intelligence Service for FALSO AI Companion.

Provides structured project context and Git status by reusing the filesystem indexer
and executing read-only Git status commands with 2.0s TTL caching.
"""

from __future__ import annotations

import logging
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.services.filesystem_indexer import filesystem_indexer

logger = logging.getLogger(__name__)


class WorkspaceIntelligenceService:
    def __init__(self, workspace_path: str = "c:/Users/Admin/Project-Falso") -> None:
        self.workspace_path = Path(workspace_path).resolve()
        self._cached_intelligence: Optional[Dict[str, Any]] = None
        self._cache_time: float = 0.0

    def get_intelligence(self) -> Dict[str, Any]:
        """Returns normalized workspace intelligence with 2.0s caching."""
        now = time.time()
        if self._cached_intelligence and (now - self._cache_time) < 2.0:
            return self._cached_intelligence

        git_info = self._get_git_details()
        recent_indexed = filesystem_indexer.get_recent(limit=10)
        recent_files = [f["name"] for f in recent_indexed if not f.get("is_dir")]

        intel = {
            "project_name": self.workspace_path.name,
            "project_root": str(self.workspace_path),
            "git_branch": git_info["branch"],
            "git_status_clean": git_info["clean"],
            "uncommitted_count": git_info["uncommitted_count"],
            "modified_files": git_info["modified_files"],
            "latest_commit": git_info["latest_commit"],
            "recent_commits": git_info["recent_commits"],
            "recent_files": recent_files[:8],
            "detected_at": now,
        }
        self._cached_intelligence = intel
        self._cache_time = now
        return intel

    def _get_git_details(self) -> Dict[str, Any]:
        """Runs read-only, non-destructive Git commands safely."""
        branch = "main"
        clean = True
        uncommitted_count = 0
        modified_files: List[str] = []
        latest_commit = "No commits found"
        recent_commits: List[str] = []

        try:
            # 1. Branch name
            res_branch = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=self.workspace_path,
                capture_output=True,
                text=True,
                timeout=1.5,
            )
            if res_branch.returncode == 0 and res_branch.stdout.strip():
                branch = res_branch.stdout.strip()

            # 2. Status
            res_status = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=self.workspace_path,
                capture_output=True,
                text=True,
                timeout=1.5,
            )
            if res_status.returncode == 0:
                lines = [line.strip() for line in res_status.stdout.splitlines() if line.strip()]
                uncommitted_count = len(lines)
                clean = (uncommitted_count == 0)
                modified_files = [line.split(maxsplit=1)[-1] for line in lines[:10]]

            # 3. Latest Commit
            res_commit = subprocess.run(
                ["git", "log", "-1", "--format=%h - %s (%cr)"],
                cwd=self.workspace_path,
                capture_output=True,
                text=True,
                timeout=1.5,
            )
            if res_commit.returncode == 0 and res_commit.stdout.strip():
                latest_commit = res_commit.stdout.strip()

            # 4. Recent Commits
            res_recent = subprocess.run(
                ["git", "log", "-5", "--format=%h - %s (%cr)"],
                cwd=self.workspace_path,
                capture_output=True,
                text=True,
                timeout=1.5,
            )
            if res_recent.returncode == 0 and res_recent.stdout.strip():
                recent_commits = [line.strip() for line in res_recent.stdout.splitlines() if line.strip()]

        except Exception as exc:
            logger.debug("Error retrieving Git details: %s", exc)

        return {
            "branch": branch,
            "clean": clean,
            "uncommitted_count": uncommitted_count,
            "modified_files": modified_files,
            "latest_commit": latest_commit,
            "recent_commits": recent_commits,
        }

    def format_summary_for_prompt(self) -> str:
        """Formats compact workspace summary for NVIDIA prompt context injection."""
        intel = self.get_intelligence()
        status_str = "Clean" if intel["git_status_clean"] else f"{intel['uncommitted_count']} uncommitted file(s)"
        mod_str = ", ".join(intel["modified_files"][:5]) if intel["modified_files"] else "None"
        lines = [
            "[WORKSPACE INTELLIGENCE CONTEXT]",
            f"Project: {intel['project_name']} ({intel['project_root']})",
            f"Git Branch: {intel['git_branch']} | Status: {status_str}",
            f"Latest Commit: {intel['latest_commit']}",
            f"Modified Files: {mod_str}",
        ]
        return "\n".join(lines)


workspace_intelligence = WorkspaceIntelligenceService()
