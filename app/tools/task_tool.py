"""Task Tool for FALSO Personal AI Companion.

Allows the AI model to create, list, complete, or postpone user tasks and coding goals.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from app.services.task_manager import task_manager_service
from app.tools.base import Tool, ToolResult
from app.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


@ToolRegistry.register
class TaskTool(Tool):
    name = "task_manager"
    description = "Manages user tasks, deadlines, and coding goals (add, list, complete, postpone, remove)."
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["add", "list", "complete", "postpone", "remove"],
                "description": "Task management action"
            },
            "title": {
                "type": "string",
                "description": "Task title or description (for add/complete/postpone)"
            },
            "category": {
                "type": "string",
                "enum": ["today", "future", "coding_goal"],
                "description": "Task category"
            },
            "due_date": {
                "type": "string",
                "description": "Due date (YYYY-MM-DD)"
            }
        },
        "required": ["action"]
    }

    async def execute(
        self,
        action: str,
        title: str = "",
        category: str = "today",
        due_date: str = "",
        **kwargs: Any
    ) -> ToolResult:
        if action == "add":
            if not title:
                return ToolResult(success=False, data=None, error="Title is required to add a task.")
            t = task_manager_service.add_task(title=title, category=category, due_date=due_date)
            return ToolResult(success=True, data=t, error=None)

        elif action == "list":
            tasks = task_manager_service.list_tasks(category=category if category != "today" else None)
            return ToolResult(success=True, data=tasks, error=None)

        elif action == "complete":
            ok = task_manager_service.complete_task(title)
            return ToolResult(success=ok, data={"completed": ok, "target": title}, error=None if ok else "Task not found")

        elif action == "postpone":
            ok = task_manager_service.postpone_task(title, due_date)
            return ToolResult(success=ok, data={"postponed": ok, "target": title}, error=None if ok else "Task not found")

        elif action == "remove":
            ok = task_manager_service.remove_task(title)
            return ToolResult(success=ok, data={"removed": ok, "target": title}, error=None if ok else "Task not found")

        return ToolResult(success=False, data=None, error=f"Unsupported action '{action}'")
