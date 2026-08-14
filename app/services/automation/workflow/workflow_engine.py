"""
Multi-Step Web Workflow Engine for FALSO (FALSO 4.8).

Manages state-machine workflows, step verification, adaptive recovery,
WAITING_USER confirmation gates, resumable workflows, cancellation, and audit logging.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from app.services.automation.browser.browser_action_registry import StructuredBrowserAction
from app.services.automation.browser.browser_engine import browser_engine
from app.services.automation.browser.page_observation import page_observer
from app.services.automation.permissions import permission_manager
from app.services.automation.workflow.workflow_models import (
    BrowserContextState,
    WorkflowResult,
    WorkflowState,
    WorkflowStep,
    WorkflowStepState,
)
from app.services.automation.workflow.workflow_planner import workflow_planner

logger = logging.getLogger(__name__)


class WorkflowEngine:
    """Stateful, adaptive, multi-step Web Workflow Engine."""

    def __init__(self) -> None:
        self.active_workflow_id: Optional[str] = None
        self.session_id: str = "DEFAULT-SESSION"
        self.originating_request_id: str = "FALSO-REQ-000"
        self.state: WorkflowState = WorkflowState.COMPLETED
        self.steps: List[WorkflowStep] = []
        self.current_step_index: int = 0
        self.browser_context: BrowserContextState = BrowserContextState()
        self.active_task_id: Optional[str] = None
        self.goal: str = ""

    def is_workflow_active(self) -> bool:
        return self.state in (
            WorkflowState.PLANNING, WorkflowState.EXECUTING,
            WorkflowState.VERIFYING, WorkflowState.RECOVERING,
            WorkflowState.WAITING_USER
        )

    def is_waiting_user(self) -> bool:
        return self.state == WorkflowState.WAITING_USER

    def cancel_workflow(self) -> str:
        """Instantly cancel active workflow and queued steps."""
        logger.warning("[WORKFLOW][CANCEL] Workflow '%s' cancelled by user command.", self.active_workflow_id)
        if self.active_task_id:
            permission_manager.revoke_task_capabilities(self.active_task_id)

        for step in self.steps:
            if step.status in (WorkflowStepState.PENDING, WorkflowStepState.EXECUTING):
                step.status = WorkflowStepState.CANCELLED

        self.state = WorkflowState.CANCELLED
        self.active_workflow_id = None
        return "Cancelled."

    def run_workflow(
        self,
        goal: str,
        task_id: Optional[str] = None,
        session_id: Optional[str] = None,
        request_id: Optional[str] = None
    ) -> WorkflowResult:
        """Initiate and execute a multi-step web workflow."""
        t_start = time.perf_counter()
        w_id = task_id or f"WORKFLOW-{int(time.time() * 1000)}"
        self.active_workflow_id = w_id
        self.active_task_id = w_id
        self.session_id = session_id or "DEFAULT-SESSION"
        self.originating_request_id = request_id or f"FALSO-REQ-{int(time.time()*1000)}"
        self.goal = goal
        self.state = WorkflowState.PLANNING

        logger.info("[WORKFLOW][START] task_id=%s session_id=%s goal=%r", w_id, self.session_id, goal)

        # 1. Dynamic Adaptive Planning
        self.steps = workflow_planner.plan_workflow(goal, self.browser_context, self.session_id, workflow_id=w_id)
        self.current_step_index = 0
        logger.info("[WORKFLOW][PLAN] Planned %d steps for workflow '%s'", len(self.steps), w_id)

        # Grant task capability
        permission_manager.grant_task_capability(w_id, "browser.interact")
        permission_manager.grant_task_capability(w_id, "browser.navigate")
        permission_manager.grant_task_capability(w_id, "browser.open")

        return self._execute_steps(t_start)

    def resume_workflow(
        self,
        user_confirmation: str = "yes",
        session_id: Optional[str] = None,
        request_id: Optional[str] = None
    ) -> WorkflowResult:
        """Resume a workflow paused in WAITING_USER state."""
        t_start = time.perf_counter()
        if not self.is_waiting_user() or (session_id and session_id != self.session_id):
            logger.warning("[WORKFLOW][RESUME] Attempted to resume workflow but state is %s or session mismatch.", self.state)
            return WorkflowResult(
                workflow_id=self.active_workflow_id or "NONE",
                session_id=self.session_id,
                originating_request_id=self.originating_request_id,
                goal=self.goal,
                state=self.state,
                steps=self.steps,
                final_message="No workflow waiting for user confirmation.",
                browser_context=self.browser_context,
            )

        logger.info("[WORKFLOW][RESUME] Resuming workflow '%s' from step %d after confirmation.", self.active_workflow_id, self.current_step_index + 1)
        if self.current_step_index < len(self.steps):
            self.steps[self.current_step_index].requires_confirmation = False
        self.state = WorkflowState.EXECUTING
        return self._execute_steps(t_start)

    def _execute_steps(self, t_start: float) -> WorkflowResult:
        """Execute remaining workflow steps sequentially with verification & recovery."""
        final_msg = "Done."

        while self.current_step_index < len(self.steps):
            if self.state == WorkflowState.CANCELLED:
                break

            step = self.steps[self.current_step_index]
            logger.info("[WORKFLOW][STEP_START] Step %d/%d: action=%s target=%r", step.step_id, len(self.steps), step.action, step.target)

            step.status = WorkflowStepState.EXECUTING
            step.attempt_count += 1
            t_step = time.perf_counter()

            # Handle Confirmation Gate (e.g. submit_form)
            if step.requires_confirmation and self.state != WorkflowState.RECOVERING:
                self.state = WorkflowState.WAITING_USER
                step.status = WorkflowStepState.PENDING
                logger.info("[WORKFLOW][WAITING_USER] Step %d requires user confirmation. Workflow paused.", step.step_id)
                return WorkflowResult(
                    workflow_id=self.active_workflow_id or "NONE",
                    session_id=self.session_id,
                    originating_request_id=self.originating_request_id,
                    goal=self.goal,
                    state=WorkflowState.WAITING_USER,
                    steps=self.steps,
                    final_message="The form is filled and ready to submit. Submit it?",
                    browser_context=self.browser_context,
                    duration_ms=(time.perf_counter() - t_start) * 1000.0,
                )

            # Map to StructuredBrowserAction
            struct_act = StructuredBrowserAction(
                action=step.action,
                target=step.target,
                capability=step.capability,
                requires_confirmation=step.requires_confirmation,
            )

            # Execute via BrowserEngine
            res = browser_engine.execute_browser_action(struct_act, task_id=self.active_task_id)
            step.before_state = res.get("before_state", {})
            step.after_state = res.get("after_state", {})
            step.duration_ms = (time.perf_counter() - t_step) * 1000.0

            # Step Verification - Anti-Fake Success Enforcement
            if res.get("verified", False):
                step.status = WorkflowStepState.COMPLETED
                step.verification = res.get("verification_reason", "Verified PASS")
                logger.info("[WORKFLOW][VERIFY] Step %d PASS: %s", step.step_id, step.verification)
                final_msg = res.get("result_text", "Done.")
                self.current_step_index += 1
            else:
                # Adaptive Recovery Attempt
                logger.warning("[WORKFLOW][RECOVERY] Step %d failed (%s). Attempting safe recovery...", step.step_id, res.get("verification_reason"))
                if step.attempt_count <= 1:
                    self.state = WorkflowState.RECOVERING
                    # Re-observe page
                    self.browser_context.last_observation_timestamp = time.time()
                    retry_res = browser_engine.execute_browser_action(struct_act, task_id=self.active_task_id)
                    if retry_res.get("verified", False):
                        step.status = WorkflowStepState.COMPLETED
                        step.verification = "Recovered & Verified PASS"
                        logger.info("[WORKFLOW][RECOVERY] Step %d RECOVERED successfully.", step.step_id)
                        final_msg = retry_res.get("result_text", "Done.")
                        self.current_step_index += 1
                    else:
                        step.status = WorkflowStepState.FAILED
                        step.verification = f"Failed: {retry_res.get('verification_reason')}"
                        self.state = WorkflowState.FAILED
                        logger.error("[WORKFLOW][FAIL] Workflow '%s' failed at step %d.", self.active_workflow_id, step.step_id)
                        return WorkflowResult(
                            workflow_id=self.active_workflow_id or "NONE",
                            session_id=self.session_id,
                            originating_request_id=self.originating_request_id,
                            goal=self.goal,
                            state=WorkflowState.FAILED,
                            steps=self.steps,
                            final_message="I couldn't complete that.",
                            browser_context=self.browser_context,
                            duration_ms=(time.perf_counter() - t_start) * 1000.0,
                        )
                else:
                    step.status = WorkflowStepState.FAILED
                    self.state = WorkflowState.FAILED
                    return WorkflowResult(
                        workflow_id=self.active_workflow_id or "NONE",
                        session_id=self.session_id,
                        originating_request_id=self.originating_request_id,
                        goal=self.goal,
                        state=WorkflowState.FAILED,
                        steps=self.steps,
                        final_message="I couldn't complete that.",
                        browser_context=self.browser_context,
                        duration_ms=(time.perf_counter() - t_start) * 1000.0,
                    )

        total_ms = (time.perf_counter() - t_start) * 1000.0
        self.state = WorkflowState.COMPLETED
        logger.info("[WORKFLOW][COMPLETE] Workflow '%s' completed successfully in %.2fms", self.active_workflow_id, total_ms)

        return WorkflowResult(
            workflow_id=self.active_workflow_id or "NONE",
            session_id=self.session_id,
            originating_request_id=self.originating_request_id,
            goal=self.goal,
            state=WorkflowState.COMPLETED,
            steps=self.steps,
            final_message=final_msg,
            browser_context=self.browser_context,
            duration_ms=total_ms,
        )


workflow_engine = WorkflowEngine()
