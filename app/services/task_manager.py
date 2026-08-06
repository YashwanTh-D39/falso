"""Tasks & Goals Management Service for FALSO Personal AI Companion.

Manages today's tasks, future tasks, coding goals, deadlines, and completion progress.
Persisted locally in `data/tasks.json`.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

TASKS_PATH = Path("data/tasks.json")

DEFAULT_TASKS: List[Dict[str, Any]] = [
    {
        "id": "task_1",
        "title": "Build FALSO Personal AI Companion",
        "category": "coding_goal",
        "status": "in_progress",
        "due_date": "2026-08-07",
        "created_at": time.time()
    },
    {
        "id": "task_2",
        "title": "Verify Silero VAD TTS interruption unit tests",
        "category": "today",
        "status": "completed",
        "due_date": "2026-08-07",
        "created_at": time.time()
    }
]


class TaskManagerService:
    def __init__(self, file_path: Path = TASKS_PATH) -> None:
        self.file_path = file_path
        self.tasks: List[Dict[str, Any]] = self._load()

    def _load(self) -> List[Dict[str, Any]]:
        if not self.file_path.exists():
            self.file_path.parent.mkdir(parents=True, exist_ok=True)
            self._save_to_disk(DEFAULT_TASKS)
            return list(DEFAULT_TASKS)

        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as exc:
            logger.warning("Failed to load tasks from %s (%s). Using defaults.", self.file_path, exc)
            return list(DEFAULT_TASKS)

    def _save_to_disk(self, data: List[Dict[str, Any]]) -> None:
        try:
            self.file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as exc:
            logger.error("Failed to save tasks to %s: %s", self.file_path, exc)

    def list_tasks(self, category: Optional[str] = None, status: Optional[str] = None) -> List[Dict[str, Any]]:
        results = self.tasks
        if category:
            results = [t for t in results if t.get("category") == category]
        if status:
            results = [t for t in results if t.get("status") == status]
        return results

    def add_task(self, title: str, category: str = "today", due_date: str = "") -> Dict[str, Any]:
        new_task = {
            "id": f"task_{uuid.uuid4().hex[:8]}",
            "title": title,
            "category": category,
            "status": "pending",
            "due_date": due_date or time.strftime("%Y-%m-%d"),
            "created_at": time.time()
        }
        self.tasks.append(new_task)
        self._save_to_disk(self.tasks)
        return new_task

    def complete_task(self, task_id: str) -> bool:
        for t in self.tasks:
            if t["id"] == task_id or task_id.lower() in t["title"].lower():
                t["status"] = "completed"
                t["completed_at"] = time.time()
                self._save_to_disk(self.tasks)
                return True
        return False

    def postpone_task(self, task_id: str, new_due_date: str = "") -> bool:
        for t in self.tasks:
            if t["id"] == task_id or task_id.lower() in t["title"].lower():
                t["status"] = "postponed"
                if new_due_date:
                    t["due_date"] = new_due_date
                self._save_to_disk(self.tasks)
                return True
        return False

    def remove_task(self, task_id: str) -> bool:
        initial_len = len(self.tasks)
        self.tasks = [t for t in self.tasks if t["id"] != task_id and task_id.lower() not in t["title"].lower()]
        if len(self.tasks) < initial_len:
            self._save_to_disk(self.tasks)
            return True
        return False

    def format_summary_for_prompt(self) -> str:
        """Formats active tasks for system prompt context injection."""
        pending = [t for t in self.tasks if t.get("status") in ("pending", "in_progress")]
        if not pending:
            return "No pending tasks."
        lines = [f"- [{t['category'].upper()}] {t['title']} (Due: {t.get('due_date', 'N/A')})" for t in pending[:5]]
        return "Active Tasks & Goals:\n" + "\n".join(lines)


task_manager_service = TaskManagerService()
