"""REST API routes for Tasks & Goals management."""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.services.task_manager import task_manager_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/tasks", tags=["Tasks"])


class TaskCreateRequest(BaseModel):
    title: str
    category: str = "today"
    due_date: str = ""


class TaskUpdateRequest(BaseModel):
    action: str  # complete, postpone, remove
    new_due_date: str = ""


@router.get("/")
async def list_tasks(category: Optional[str] = None, status: Optional[str] = None):
    """Returns stored tasks matching optional filters."""
    return task_manager_service.list_tasks(category=category, status=status)


@router.post("/")
async def create_task(request: TaskCreateRequest):
    """Creates a new task or coding goal."""
    return task_manager_service.add_task(
        title=request.title,
        category=request.category,
        due_date=request.due_date
    )


@router.put("/{task_id}")
async def update_task(task_id: str, request: TaskUpdateRequest):
    """Updates task state: complete, postpone, or remove."""
    if request.action == "complete":
        ok = task_manager_service.complete_task(task_id)
    elif request.action == "postpone":
        ok = task_manager_service.postpone_task(task_id, request.new_due_date)
    elif request.action == "remove":
        ok = task_manager_service.remove_task(task_id)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown task action '{request.action}'"
        )
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task '{task_id}' not found"
        )
    return {"ok": True, "action": request.action}


@router.delete("/{task_id}")
async def delete_task(task_id: str):
    """Deletes a task by ID."""
    ok = task_manager_service.remove_task(task_id)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task '{task_id}' not found"
        )
    return {"ok": True}
