"""
FALSO 4.1 Adaptive Autonomous Task Intelligence Engine.

Implements real-time task status tracking & lifecycle management:
IDLE -> OBSERVING -> PLANNING -> WAITING_PERMISSION -> EXECUTING -> VERIFYING -> RECOVERING -> PAUSED -> COMPLETED / FAILED / CANCELLED

Features:
- State -> Goal Reasoning & Precondition/Postcondition Awareness
- Failure Classification (TRANSIENT, CONFIGURATION, APPLICATION, ENVIRONMENT, PERMISSION, UNKNOWN)
- Task Pause / Resume & Status Query Support ("FALSO pause", "FALSO resume", "FALSO what are you doing?")
- Task-Scoped Capability Isolation & Automatic Revocation on Completion
- Project Health Development Agent Workflow ("make my project healthy")
- Strict Security (DENY-by-default, sandbox protection, secret masking)
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
import enum
import logging
import os
from pathlib import Path
import time
from typing import Any

from app.services.automation.goal_planner import (
    FailureType,
    goal_planner,
    PlanStep,
    TaskPlan,
)
from app.services.automation.permissions import (
    FileOperation,
    PermissionLevel,
    permission_manager,
    RiskLevel,
)
from app.services.automation.windows.executor import windows_executor
from app.services.automation.windows.process_manager import process_manager
from app.services.automation.windows.window_manager import window_manager
from app.services.context_detector import context_detector
from app.services.workspace_intelligence import workspace_intelligence
from app.tools.manager import ToolManager

logger = logging.getLogger(__name__)

# Safety Budget Limits
MAX_ACTIONS = 50
MAX_REPAIR_ITERATIONS = 5
MAX_REPLANS = 5
MAX_RUNTIME = 600.0  # 10 minutes max runtime
MAX_ACTION_RETRIES = 2


class OperatingMode(enum.Enum):
    NORMAL = "NORMAL"
    AUTOPILOT = "AUTOPILOT"


class TaskStatus(enum.Enum):
    IDLE = "IDLE"
    OBSERVING = "OBSERVING"
    PLANNING = "PLANNING"
    WAITING_PERMISSION = "WAITING_PERMISSION"
    EXECUTING = "EXECUTING"
    VERIFYING = "VERIFYING"
    RECOVERING = "RECOVERING"
    PAUSED = "PAUSED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


@dataclass
class TaskState:
    task_id: str
    goal: str
    status: TaskStatus = TaskStatus.IDLE
    start_time: float = field(default_factory=time.time)
    end_time: float | None = None
    action_count: int = 0
    repair_iterations: int = 0
    replans: int = 0
    current_step: int = 0
    completed_steps: list[str] = field(default_factory=list)
    failed_steps: list[str] = field(default_factory=list)
    current_observation: dict[str, Any] = field(default_factory=dict)
    next_action: str | None = None
    error_message: str | None = None
    failure_classification: FailureType = FailureType.NONE


class AutopilotAgent:
    """FALSO 4.1 Adaptive Autonomous Computer Agent Core."""

    def __init__(self, tool_manager: ToolManager | None = None) -> None:
        self.tool_manager = tool_manager or ToolManager()
        self.mode: OperatingMode = OperatingMode.NORMAL
        self.active_task: TaskState | None = None
        self.task_queue: list[TaskState] = []
        self.completed_tasks: list[TaskState] = []
        self._cancel_event = asyncio.Event()
        self._pause_event = asyncio.Event()

    def is_autopilot_active(self) -> bool:
        return self.mode == OperatingMode.AUTOPILOT and self.active_task is not None

    def pause_active_task(self) -> str:
        """Pause active automation task while preserving state."""
        if self.active_task and self.active_task.status not in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED):
            self._pause_event.set()
            self.active_task.status = TaskStatus.PAUSED
            logger.info("[AUTOPILOT] Task '%s' PAUSED by user.", self.active_task.task_id)
            return "Automation paused."
        return "No active automation task to pause."

    def resume_active_task(self) -> str:
        """Resume a paused automation task."""
        if self.active_task and self.active_task.status == TaskStatus.PAUSED:
            self._pause_event.clear()
            self.active_task.status = TaskStatus.EXECUTING
            logger.info("[AUTOPILOT] Task '%s' RESUMED by user.", self.active_task.task_id)
            return "Resuming automation."
        return "No paused task to resume."

    def get_task_status_summary(self) -> str:
        """Return concise state summary for user queries ('FALSO, what are you doing?')."""
        if not self.active_task or self.active_task.status in (TaskStatus.IDLE, TaskStatus.COMPLETED):
            return "Automation is currently idle."
        if self.active_task.status == TaskStatus.PAUSED:
            return "Automation is currently paused."
        if self.active_task.status == TaskStatus.OBSERVING:
            return "I'm observing the computer state."
        if self.active_task.status == TaskStatus.PLANNING:
            return "I'm planning the required steps."
        if self.active_task.status in (TaskStatus.EXECUTING, TaskStatus.VERIFYING):
            return f"I'm executing step: {self.active_task.goal}."
        if self.active_task.status == TaskStatus.RECOVERING:
            return "I'm recovering from a step failure."
        return "Working on your goal."

    def get_task_history_summary(self) -> str:
        """Return concise task history summary ('FALSO, what happened?')."""
        if self.completed_tasks:
            last = self.completed_tasks[-1]
            if last.completed_steps:
                return f"Last task completed: {last.completed_steps[-1]}."
            return f"Last task '{last.goal}' ended with status {last.status.value}."
        return "No prior automation tasks recorded."

    def cancel_active_task(self) -> str:
        """Instantly cancel current autopilot automation and revoke task capabilities."""
        self._cancel_event.set()
        self._pause_event.clear()
        if self.active_task:
            self.active_task.status = TaskStatus.CANCELLED
            self.active_task.end_time = time.time()
            permission_manager.revoke_task_capabilities(self.active_task.task_id)
            logger.warning("[AUTOPILOT] Task '%s' cancelled by user command.", self.active_task.task_id)
        self.mode = OperatingMode.NORMAL
        return "Cancelled."

    async def run_goal(self, goal: str, task_id: str | None = None, session_id: str | None = None) -> str:
        """Execute a natural-language goal through the adaptive agentic loop."""
        tid = task_id or f"AUTOPILOT-{int(time.time() * 1000)}"
        task = TaskState(task_id=tid, goal=goal, status=TaskStatus.PLANNING)
        plan = None

        self.active_task = task
        self.mode = OperatingMode.AUTOPILOT
        self._cancel_event.clear()
        self._pause_event.clear()

        # Grant task-scoped capability
        permission_manager.grant_task_capability(tid, "windows.interact")

        logger.info("[AUTOMATION][REQUEST] task_id=%s goal=%r", tid, goal)
        goal_lower = goal.lower().strip()

        # DANGEROUS COMMAND REJECTION GATE
        if any(w in goal_lower for w in ("delete c:\\windows", "delete system32", "disable windows security", "execute arbitrary .exe", "read my .env")):
            task.status = TaskStatus.FAILED
            task.error_message = "Dangerous action rejected by PermissionManager."
            permission_manager.revoke_task_capabilities(tid)
            self.completed_tasks.append(task)
            self.active_task = None
            self.mode = OperatingMode.NORMAL
            return "I couldn't complete that safely."

        try:
            # ── DEDICATED WORKFLOWS ──
            if "healthy" in goal_lower or ("make" in goal_lower and "project" in goal_lower):
                success = await self._workflow_make_project_healthy(task)
            elif "prepare" in goal_lower and ("environment" in goal_lower or "coding" in goal_lower or "falso" in goal_lower):
                success = await self._workflow_prepare_dev_environment(task)
            elif "downloads" in goal_lower and ("organize" in goal_lower or "clean" in goal_lower):
                success = await self._workflow_organize_downloads(task)
            elif "run" in goal_lower and "test" in goal_lower:
                success = await self._workflow_run_and_fix_tests(task)
            else:
                # 1. OBSERVING
                task.status = TaskStatus.OBSERVING
                logger.info("[AUTOMATION][INTENT] task_id=%s intent=AUTOMATION", tid)
                obs = self._observe_pc()
                task.current_observation = obs
                logger.info("[AUTOMATION][OBSERVE] task_id=%s active_app=%s", tid, obs.get("active_app"))

                # 2. PLANNING
                task.status = TaskStatus.PLANNING
                plan = goal_planner.create_plan(goal, obs, session_id=session_id)
                logger.info("[AUTOMATION][PLAN] task_id=%s steps=%d", tid, len(plan.steps))

                success = True
                for step in plan.steps:
                    # Check pause
                    while self._pause_event.is_set():
                        await asyncio.sleep(0.2)
                        if self._cancel_event.is_set():
                            task.status = TaskStatus.CANCELLED
                            return "Cancelled."

                    # Check interruption
                    if self._cancel_event.is_set():
                        task.status = TaskStatus.CANCELLED
                        return "Cancelled."

                    # Action & Runtime Budget check
                    elapsed = time.time() - task.start_time
                    if task.action_count >= MAX_ACTIONS or elapsed >= MAX_RUNTIME:
                        logger.warning("[AUTOPILOT][%s] Safety budget exceeded", tid)
                        task.status = TaskStatus.FAILED
                        task.error_message = "Safety budget limit reached."
                        return "I couldn't complete that safely."

                    # 3. WAITING_PERMISSION & RISK GATE
                    task.status = TaskStatus.WAITING_PERMISSION
                    action_id = f"step_{step.id}_{step.action}"
                    risk = permission_manager.get_risk_level(step.action, step.target, step.params)
                    logger.info("[AUTOMATION][PERMISSION] task_id=%s action_id=%s risk=%s", tid, action_id, risk.value)
                    if risk == RiskLevel.HIGH:
                        logger.warning("[AUTOMATION][PERMISSION] task_id=%s action_id=%s DENIED high_risk", tid, action_id)
                        task.status = TaskStatus.FAILED
                        task.error_message = "High risk action requires confirmation."
                        return "I need permission for that action."

                    perm = permission_manager.check_capability(f"windows.{step.action}", target=step.target, task_id=tid)
                    if not perm.allowed:
                        logger.warning("[AUTOMATION][PERMISSION] task_id=%s action_id=%s DENIED reason=%s", tid, action_id, perm.reason)
                        task.status = TaskStatus.FAILED
                        task.error_message = perm.reason
                        task.failure_classification = FailureType.PERMISSION
                        return "I couldn't complete that safely."

                    # 4. EXECUTING
                    task.status = TaskStatus.EXECUTING
                    task.action_count += 1
                    logger.info("[AUTOMATION][EXECUTE] task_id=%s action_id=%s action=%s target=%s", tid, action_id, step.action, step.target)
                    exec_kwargs = {
                        "app": step.target,
                        "title": step.target,
                        "target": step.target,
                        "url": step.params.get("url", step.target),
                        "text": step.params.get("text", ""),
                        "path": step.target,
                        "x": step.params.get("x"),
                        "y": step.params.get("y"),
                    }
                    exec_kwargs.update(step.params)
                    res = windows_executor.execute_action(
                        step.action,
                        task_id=tid,
                        **exec_kwargs,
                    )

                    # Check for unsaved changes return
                    if res.get("unsaved_changes"):
                        task.status = TaskStatus.FAILED
                        target_title = step.target.capitalize()
                        resp = f"{target_title} has unsaved changes. I won't close it without confirmation."
                        logger.warning("[AUTOMATION][UNSAVED_CHANGES] task_id=%s target=%s", tid, step.target)
                        return resp

                    if res.get("result") is not None and step.action in ("interact_with_app", "calculate"):
                        task.last_result = res.get("result")

                    # 5. VERIFYING
                    task.status = TaskStatus.VERIFYING
                    post_obs = self._observe_pc()
                    task.current_observation = post_obs
                    active_win = post_obs.get("active_window", "Unknown")
                    logger.info("[AUTOMATION][WINDOW] task_id=%s action_id=%s active_window=%s", tid, action_id, active_win)
                    logger.info("[AUTOMATION][VERIFY] task_id=%s action_id=%s success=%s", tid, action_id, res.get("success"))

                    if step.action in ("close_window", "close_app"):
                        # Close: verified only if execution succeeded AND window is confirmed absent
                        verified = res.get("verified", False) and not window_manager.is_window_open(step.target)
                    else:
                        # All other actions: verified only by authoritative verification result
                        # Window/process existence alone is NEVER sufficient verification
                        verified = res.get("verified", False)

                    if verified:
                        task.completed_steps.append(f"Step {step.id}: {step.action} ({step.target}) Verified")
                        try:
                            from app.services.automation.operator import VerifiedActionRecord, operator_engine
                            operator_engine._current_state.add_verified_action(
                                VerifiedActionRecord(
                                    task_id=tid,
                                    action_id=f"step_{step.id}",
                                    target=step.target,
                                    action=step.action,
                                    verification_result=(True, "Verified"),
                                    safe_summary=f"{step.action} on {step.target}",
                                )
                            )
                        except Exception:
                            pass
                    else:
                        # 6. RECOVERING (Max 2 attempts, failure classification)
                        task.status = TaskStatus.RECOVERING
                        task.failure_classification = FailureType.APPLICATION
                        logger.warning("[AUTOMATION][ERROR] task_id=%s action_id=%s Verification failed — Entering RECOVERING", tid, action_id)
                        recovered = False

                        for retry in range(1, MAX_ACTION_RETRIES + 1):
                            if self._cancel_event.is_set():
                                task.status = TaskStatus.CANCELLED
                                return "Cancelled."

                            # 1. Observe state before retry
                            obs_before = self._observe_pc()

                            # 2. Re-attempt the actual action with explicit target
                            exec_params = dict(step.params)
                            if "target" not in exec_params:
                                exec_params["target"] = step.target
                            retry_res = windows_executor.execute_action(step.action, task_id=tid, **exec_params)

                            # 3. Observe state after retry
                            obs_after = self._observe_pc()
                            task.current_observation = obs_after

                            # 4. Authoritative verification of the retried action
                            if step.action in ("close_window", "close_app"):
                                retry_verified = retry_res.get("verified", False) and not window_manager.is_window_open(step.target)
                            else:
                                retry_verified = retry_res.get("verified", False)

                            if retry_verified:
                                recovered = True
                                if retry_res.get("result") is not None and step.action in ("interact_with_app", "calculate"):
                                    task.last_result = retry_res.get("result")
                                task.completed_steps.append(f"Step {step.id}: Recovered on retry {retry}")
                                break

                        if not recovered:
                            task.failed_steps.append(f"Step {step.id}: {step.action} ({step.target}) Failed")
                            success = False
                            break

            task.end_time = time.time()
            if self._cancel_event.is_set() or task.status == TaskStatus.CANCELLED:
                task.status = TaskStatus.CANCELLED
                return "Cancelled."

            if success:
                task.status = TaskStatus.COMPLETED
                last_res = getattr(task, "last_result", None)
                steps_list = getattr(plan, "steps", None)
                last_target = steps_list[-1].target if (steps_list and len(steps_list) > 0) else ""
                resp = self._concise_completion_response(goal_lower, calc_result=last_res, target_app=last_target)
                logger.info("[AUTOMATION][COMPLETE] task_id=%s result=%s", tid, resp)
                return resp
            else:
                task.status = TaskStatus.FAILED
                resp = self._concise_failure_response(goal_lower, task.error_message)
                logger.warning("[AUTOMATION][ERROR] task_id=%s result=%s", tid, resp)
                return resp

        except Exception as e:
            logger.exception("[AUTOMATION][ERROR] task_id=%s exception=%s", tid, type(e).__name__)
            task.status = TaskStatus.FAILED
            task.error_message = str(e)
            task.failure_classification = FailureType.UNKNOWN
            return self._concise_failure_response(goal_lower, task.error_message)

        finally:
            permission_manager.revoke_task_capabilities(tid)
            self.completed_tasks.append(task)
            self.active_task = None
            self.mode = OperatingMode.NORMAL

    async def _workflow_make_project_healthy(self, task: TaskState) -> bool:
        """NOT_IMPLEMENTED: Requires real pytest execution and server verification."""
        logger.warning("[AUTOPILOT] STUB WORKFLOW: _workflow_make_project_healthy is NOT_IMPLEMENTED")
        task.status = TaskStatus.FAILED
        task.error_message = "NOT_IMPLEMENTED"
        return False

    async def _workflow_prepare_dev_environment(self, task: TaskState) -> bool:
        """NOT_IMPLEMENTED: Requires real VS Code launch, pytest execution, and server verification."""
        logger.warning("[AUTOPILOT] STUB WORKFLOW: _workflow_prepare_dev_environment is NOT_IMPLEMENTED")
        task.status = TaskStatus.FAILED
        task.error_message = "NOT_IMPLEMENTED"
        return False

    async def _workflow_organize_downloads(self, task: TaskState) -> bool:
        """NOT_IMPLEMENTED: Requires real file classification and move operations."""
        logger.warning("[AUTOPILOT] STUB WORKFLOW: _workflow_organize_downloads is NOT_IMPLEMENTED")
        task.status = TaskStatus.FAILED
        task.error_message = "NOT_IMPLEMENTED"
        return False

    async def _workflow_run_and_fix_tests(self, task: TaskState) -> bool:
        """NOT_IMPLEMENTED: Requires real pytest subprocess execution and output parsing."""
        logger.warning("[AUTOPILOT] STUB WORKFLOW: _workflow_run_and_fix_tests is NOT_IMPLEMENTED")
        task.status = TaskStatus.FAILED
        task.error_message = "NOT_IMPLEMENTED"
        return False

    @staticmethod
    def _concise_completion_response(goal_lower: str, calc_result: Any = None, target_app: str = "") -> str:
        """Generate a concise, user-facing completion response based on the goal and verified target."""
        if calc_result is not None:
            return f"{calc_result}."

        target_clean = target_app.lower()
        if "close" in goal_lower or "exit" in goal_lower or "quit" in goal_lower:
            if "claude" in goal_lower or target_clean == "claude":
                return "Claude is closed."
            if "chrome" in goal_lower or target_clean == "chrome":
                return "Chrome is closed."
            if "notepad" in goal_lower or target_clean == "notepad":
                return "Notepad is closed."
            if "calculator" in goal_lower or "calc" in goal_lower or target_clean == "calculator":
                return "Calculator is closed."
            if "explorer" in goal_lower or "project-falso" in goal_lower or "project" in goal_lower or target_clean == "file explorer":
                return "File Explorer is closed."
            return f"{target_app or 'Application'} is closed."

        if "claude" in goal_lower or target_clean == "claude":
            return "Claude is open."
        if "chrome" in goal_lower or target_clean == "chrome":
            return "Chrome is open."
        if "notepad" in goal_lower or target_clean == "notepad":
            return "Notepad is open."
        if "calculator" in goal_lower or "calc" in goal_lower or target_clean == "calculator":
            return "Calculator is open."
        if "explorer" in goal_lower or "project-falso" in goal_lower or "project" in goal_lower or target_clean == "file explorer":
            return "File Explorer is open."
        if "test" in goal_lower or "pytest" in goal_lower:
            return "Tests completed."
        if "browser" in goal_lower or "localhost" in goal_lower:
            return "Browser is open."
        if "code" in goal_lower or "vscode" in goal_lower or "vs code" in goal_lower:
            return "VS Code is open."
        return "Done."

    @staticmethod
    def _concise_failure_response(goal_lower: str, error_message: str | None = None) -> str:
        """Generate a concise, user-facing failure response based on the goal."""
        if error_message == "NOT_IMPLEMENTED" or any(w in goal_lower for w in ("healthy", "downloads", "environment", "run and fix")):
            return "I can't automate that yet."
        if "chrome" in goal_lower:
            return "I couldn't open Chrome."
        if "notepad" in goal_lower:
            return "I couldn't open Notepad."
        if "calculator" in goal_lower or "calc" in goal_lower:
            return "I couldn't open Calculator."
        if "explorer" in goal_lower or "project-falso" in goal_lower or "project" in goal_lower:
            return "I couldn't open File Explorer."
        if "test" in goal_lower or "pytest" in goal_lower:
            return "I couldn't run the tests."
        return "I couldn't complete that."

    def _observe_pc(self) -> dict[str, Any]:
        """Query PC metrics, active window, process perception, and workspace intelligence."""
        from app.services.automation.windows.perception import perception_engine
        tid = self.active_task.task_id if self.active_task else None
        snapshot = perception_engine.take_snapshot(task_id=tid)

        return {
            "active_app": snapshot.foreground_window.get("name", snapshot.foreground_window.get("title", "Unknown")),
            "active_window": snapshot.foreground_window.get("title", "Unknown"),
            "running_apps": [p["name"] for p in snapshot.processes if p.get("running")],
            "applications": snapshot.applications,
            "project_name": snapshot.filesystem.get("project_name", "Project-Falso"),
            "git_branch": snapshot.filesystem.get("git_branch", "main"),
            "snapshot": snapshot,
            "timestamp": snapshot.timestamp,
        }


autopilot_agent = AutopilotAgent()
