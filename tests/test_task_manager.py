"""Unit tests for TaskManagerService."""

import pytest
from pathlib import Path
from app.services.task_manager import TaskManagerService


def test_task_manager_service_crud(tmp_path: Path):
    task_file = tmp_path / "tasks.json"
    service = TaskManagerService(file_path=task_file)

    task = service.add_task(title="Refactor FALSO Spatial OS", category="coding_goal")
    assert task["title"] == "Refactor FALSO Spatial OS"
    assert task["status"] == "pending"

    # Complete
    ok = service.complete_task(task["id"])
    assert ok is True

    tasks = service.list_tasks(status="completed")
    assert any(t["id"] == task["id"] for t in tasks)

    # Delete
    deleted = service.remove_task(task["id"])
    assert deleted is True
