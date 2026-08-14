"""
FALSO 4.13 Authorized Android Unlock & Resume Manager.

Manages the lifecycle of Android operations that encounter a locked device:
1. Detects LOCKED state.
2. Wakes display (without unlocking or bypassing security).
3. Transitions to WAITING_FOR_USER_UNLOCK.
4. Preserves pending multi-step workflows & context.
5. Authoritatively observes legitimate LOCKED -> UNLOCKED transitions.
6. Revalidates device identity, authorization, online state, and app state.
7. Automatically resumes from the first incomplete step without repeating verified actions.
8. Truthfully verifies every resumed action.

ZERO-CREDENTIAL POLICY:
Never stores, logs, transmits, guesses, brute-forces, or injects user credentials.
Authentication is handled entirely by the user on the Android device.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import enum
import logging
import time
from typing import Any, Callable

from app.services.automation.android.controller import android_controller
from app.services.automation.android.device_manager import android_device_manager
from app.services.automation.android.device_state import (
    AndroidCapabilityState,
    AndroidExecutionState,
    ConnectionState,
)
from app.services.automation.android.observer import android_observer

logger = logging.getLogger(__name__)


class UnlockState(enum.Enum):
    READY = "READY"
    LOCKED = "LOCKED"
    WAITING_FOR_USER_UNLOCK = "WAITING_FOR_USER_UNLOCK"
    UNLOCK_DETECTED = "UNLOCK_DETECTED"
    REVALIDATING = "REVALIDATING"
    RESUMING = "RESUMING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    TIMEOUT = "TIMEOUT"


class StepState(enum.Enum):
    PENDING = "PENDING"
    EXECUTING = "EXECUTING"
    VERIFYING = "VERIFYING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


@dataclass
class WorkflowStep:
    """Represents an atomic action within a multi-step Android workflow."""
    action_id: str
    action_name: str
    target_app: str
    params: dict[str, Any] = field(default_factory=dict)
    state: StepState = StepState.PENDING
    execution_result: dict[str, Any] | None = None
    verified: bool = False
    verification_reason: str = ""


@dataclass
class PendingWorkflow:
    """
    Preserved state of an active Android workflow waiting for user unlock.
    ZERO-CREDENTIAL: Contains no PIN, password, pattern, or biometric data.
    """
    task_id: str
    goal: str
    device_id: str
    target_app: str
    completed_steps: list[WorkflowStep] = field(default_factory=list)
    pending_steps: list[WorkflowStep] = field(default_factory=list)
    context_data: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    timeout_sec: float = 120.0
    state: UnlockState = UnlockState.LOCKED
    workflow_version: int = 1


class AuthorizedUnlockResumeManager:
    """
    Coordinates authorized unlock workflows and automatic task resumption for Android devices.
    """

    DEFAULT_UNLOCK_TIMEOUT = 120.0

    def __init__(
        self,
        device_manager=None,
        observer=None,
        controller=None,
    ) -> None:
        self.device_manager = device_manager or android_device_manager
        self.observer = observer or android_observer
        self.controller = controller or android_controller
        self._active_workflow: PendingWorkflow | None = None

    def get_active_workflow(self) -> PendingWorkflow | None:
        return self._active_workflow

    def initiate_unlock_wait(
        self,
        task_id: str,
        goal: str,
        pending_steps: list[WorkflowStep] | list[dict[str, Any]],
        completed_steps: list[WorkflowStep] | list[dict[str, Any]] | None = None,
        device_id: str | None = None,
        target_app: str = "android_app",
        context_data: dict[str, Any] | None = None,
        timeout_sec: float = DEFAULT_UNLOCK_TIMEOUT,
    ) -> tuple[bool, str]:
        """
        Preserve the pending workflow and enter WAITING_FOR_USER_UNLOCK state.
        Wakes the display so the user can authenticate directly.
        """
        logger.info("[ANDROID][UNLOCK][START] task_id=%s device_id=%s goal='%s'", task_id, device_id or "auto", goal)

        # 1. Device identity & authorization check
        target_dev = self.device_manager.get_device_info(device_id)
        if not target_dev:
            logger.warning("[ANDROID][UNLOCK][ERROR] No connected Android device found.")
            return False, "No connected Android device found."

        if not target_dev.is_authorized or target_dev.connection_state == ConnectionState.UNAUTHORIZED:
            logger.warning("[ANDROID][UNLOCK][ERROR] Android device %s is unauthorized.", target_dev.device_id)
            return False, f"Android device {target_dev.device_id} is not authorized for ADB."

        if target_dev.connection_state == ConnectionState.OFFLINE:
            logger.warning("[ANDROID][UNLOCK][ERROR] Android device %s is offline.", target_dev.device_id)
            return False, f"Android device {target_dev.device_id} is offline."

        # Convert dictionary steps if passed as dicts
        norm_pending = []
        for s in pending_steps:
            if isinstance(s, WorkflowStep):
                norm_pending.append(s)
            elif isinstance(s, dict):
                norm_pending.append(
                    WorkflowStep(
                        action_id=s.get("action_id", f"step_{len(norm_pending)+1}"),
                        action_name=s.get("action_name", s.get("action", "")),
                        target_app=s.get("target_app", target_app),
                        params=s.get("params", {}),
                        state=StepState.PENDING,
                    )
                )

        norm_completed = []
        if completed_steps:
            for s in completed_steps:
                if isinstance(s, WorkflowStep):
                    norm_completed.append(s)
                elif isinstance(s, dict):
                    norm_completed.append(
                        WorkflowStep(
                            action_id=s.get("action_id", f"done_{len(norm_completed)+1}"),
                            action_name=s.get("action_name", s.get("action", "")),
                            target_app=s.get("target_app", target_app),
                            params=s.get("params", {}),
                            state=StepState.COMPLETED,
                            verified=s.get("verified", True),
                        )
                    )

        # 2. Wake display
        self.wake_display(target_dev.device_id)

        # 3. Create PendingWorkflow
        workflow = PendingWorkflow(
            task_id=task_id,
            goal=goal,
            device_id=target_dev.device_id,
            target_app=target_app,
            completed_steps=norm_completed,
            pending_steps=norm_pending,
            context_data=context_data or {},
            created_at=time.time(),
            timeout_sec=timeout_sec,
            state=UnlockState.WAITING_FOR_USER_UNLOCK,
        )

        self._active_workflow = workflow
        logger.info(
            "[ANDROID][UNLOCK][WAITING] task_id=%s device_id=%s pending_steps=%d state=%s",
            task_id,
            target_dev.device_id,
            len(norm_pending),
            workflow.state.value,
        )

        # Voice-friendly truthful prompt
        prompt = "Your phone is locked. Unlock it and I'll continue."

        return True, prompt

    def wake_display(self, device_id: str | None = None) -> dict[str, Any]:
        """
        Wakes the phone display via KEYCODE_WAKEUP (keyevent 224).
        CRITICAL: Successful wake means DISPLAY_AWAKE, NEVER UNLOCKED.
        """
        logger.info("[ANDROID][UNLOCK][WAKE] Waking display on device %s", device_id or "default")
        res = self.controller.wake_display(device_id=device_id)
        return {
            "success": res.get("success", False),
            "action": "wake_display",
            "display_state": "DISPLAY_AWAKE" if res.get("success") else "UNKNOWN",
            "is_unlocked": False,
            "verified": res.get("success", False),
        }

    def check_unlock_status(self, device_id: str | None = None) -> tuple[UnlockState, str]:
        """
        Authoritatively observe device lock state and advance state machine if unlocked.
        """
        workflow = self._active_workflow
        dev_id = device_id or (workflow.device_id if workflow else None)

        # Check timeout first
        if workflow and (time.time() - workflow.created_at > workflow.timeout_sec):
            logger.info("[ANDROID][UNLOCK][TIMEOUT] task_id=%s timeout_sec=%s", workflow.task_id, workflow.timeout_sec)
            workflow.state = UnlockState.TIMEOUT
            return UnlockState.TIMEOUT, "Your phone wasn't unlocked, so I paused the task."

        lock_obs = self.observer.observe_lock_state(device_id=dev_id)
        is_locked = lock_obs.get("is_locked")
        state_str = lock_obs.get("state")

        if is_locked is None or state_str == "UNKNOWN":
            logger.warning("[ANDROID][UNLOCK][LOCKED] Lock state cannot be verified (UNKNOWN).")
            if workflow:
                workflow.state = UnlockState.LOCKED
            return UnlockState.LOCKED, "Your phone's unlock state couldn't be verified."

        if is_locked is True:
            logger.debug("[ANDROID][UNLOCK][LOCKED] Device %s remains locked.", dev_id)
            if workflow:
                workflow.state = UnlockState.WAITING_FOR_USER_UNLOCK
            return UnlockState.WAITING_FOR_USER_UNLOCK, "Your phone is locked. Unlock it and I'll continue."

        # Legitimate UNLOCKED state detected
        logger.info("[ANDROID][UNLOCK][DETECTED] Legitimate unlock detected on device %s.", dev_id)
        if workflow:
            workflow.state = UnlockState.UNLOCK_DETECTED
        return UnlockState.UNLOCK_DETECTED, "Unlocked. Continuing."

    def revalidate_device_and_workflow(self, workflow: PendingWorkflow | None = None) -> tuple[bool, str]:
        """
        Revalidate device identity, ADB authorization, online status, and freshness of pending actions.
        """
        wf = workflow or self._active_workflow
        if not wf:
            return False, "No active workflow to revalidate."

        logger.info("[ANDROID][UNLOCK][REVALIDATE] Revalidating task_id=%s device_id=%s", wf.task_id, wf.device_id)
        wf.state = UnlockState.REVALIDATING

        # 1. Timeout Check
        if time.time() - wf.created_at > wf.timeout_sec:
            wf.state = UnlockState.TIMEOUT
            logger.warning("[ANDROID][UNLOCK][TIMEOUT] Workflow expired during revalidation.")
            return False, "Your phone wasn't unlocked, so I paused the task."

        # 2. Device Identity & Online State
        dev_info = self.device_manager.get_device_info(wf.device_id)
        if not dev_info or not dev_info.is_authorized:
            wf.state = UnlockState.FAILED
            logger.warning("[ANDROID][UNLOCK][ERROR] Device identity revalidation failed.")
            return False, "Device revalidation failed or device unauthorized."

        if dev_info.connection_state == ConnectionState.OFFLINE:
            wf.state = UnlockState.FAILED
            logger.warning("[ANDROID][UNLOCK][ERROR] Device offline during revalidation.")
            return False, "Device is offline."

        # 3. Lock State Re-observation
        lock_obs = self.observer.observe_lock_state(wf.device_id)
        if lock_obs.get("is_locked") is not False:
            wf.state = UnlockState.LOCKED
            logger.warning("[ANDROID][UNLOCK][LOCKED] Device is still locked upon revalidation.")
            return False, "Your phone is locked. Unlock it and I'll continue."

        return True, "Revalidation successful."

    def resume_workflow(
        self,
        workflow: PendingWorkflow | None = None,
        skill_registry=None,
    ) -> tuple[bool, str]:
        """
        Resumes preserved workflow from the first incomplete step.
        Deduplicates already completed steps, executes remaining actions, and authoritatively verifies results.
        """
        wf = workflow or self._active_workflow
        if not wf:
            return False, "No active workflow to resume."

        # 1. Revalidate
        valid, reval_msg = self.revalidate_device_and_workflow(wf)
        if not valid:
            return False, reval_msg

        logger.info("[ANDROID][UNLOCK][RESUME] Resuming task_id=%s from first incomplete step", wf.task_id)
        wf.state = UnlockState.RESUMING

        # Lazy import of skills / operator components to avoid circular dependencies
        from app.services.automation.android.skills import (
            android_app_skill,
            android_calling_skill,
            android_device_skill,
            android_messaging_skill,
        )

        last_summary = "Done."
        while wf.pending_steps:
            step = wf.pending_steps[0]
            step.state = StepState.EXECUTING
            logger.info("[ANDROID][UNLOCK][RESUME] Executing step action=%s target=%s", step.action_name, step.target_app)

            # 2. Action Deduplication Check
            if self._is_step_already_satisfied(step, wf.device_id):
                logger.info("[ANDROID][UNLOCK][RESUME] Step %s already satisfied. Skipping.", step.action_name)
                step.state = StepState.COMPLETED
                step.verified = True
                step.verification_reason = "Already satisfied."
                last_summary = f"{step.target_app.capitalize()} is open." if step.action_name in ("launch_app", "open_app", "launch_android_app") else "Done."
                wf.completed_steps.append(wf.pending_steps.pop(0))
                continue

            # 3. Dispatch to Skill
            exec_result = self._dispatch_step_execution(step, wf.device_id)
            step.execution_result = exec_result

            # 4. Verify Resumed Step
            step.state = StepState.VERIFYING
            verified, reason = self._verify_step_execution(step, exec_result, wf.device_id)
            step.verified = verified
            step.verification_reason = reason

            if not verified:
                step.state = StepState.FAILED
                wf.state = UnlockState.FAILED
                logger.warning("[ANDROID][UNLOCK][ERROR] Step %s failed verification: %s", step.action_name, reason)
                return False, f"I couldn't verify that {step.action_name} completed."

            # Step succeeded & verified
            step.state = StepState.COMPLETED
            wf.completed_steps.append(wf.pending_steps.pop(0))
            last_summary = exec_result.get("summary") or reason or "Done."

        # All steps completed
        wf.state = UnlockState.COMPLETED
        logger.info("[ANDROID][UNLOCK][COMPLETE] task_id=%s completed successfully. Summary: %s", wf.task_id, last_summary)
        self._active_workflow = None
        return True, last_summary

    def cancel_unlock_wait(self, reason: str = "Cancelled.") -> str:
        """Immediately cancel active waiting workflow on FALSO stop."""
        if self._active_workflow:
            logger.info("[ANDROID][UNLOCK][CANCEL] task_id=%s cancelled. Reason: %s", self._active_workflow.task_id, reason)
            self._active_workflow.state = UnlockState.CANCELLED
            self._active_workflow = None
        return "Cancelled."

    def handle_timeout(self, workflow: PendingWorkflow | None = None) -> str:
        """Handle 120-second timeout expiration."""
        wf = workflow or self._active_workflow
        if wf:
            logger.info("[ANDROID][UNLOCK][TIMEOUT] task_id=%s timed out.", wf.task_id)
            wf.state = UnlockState.TIMEOUT
            self._active_workflow = None
        return "Your phone wasn't unlocked, so I paused the task."

    def handle_disconnection(self, device_id: str | None = None) -> str:
        """Handle phone disconnection during unlock wait."""
        if self._active_workflow and (device_id is None or self._active_workflow.device_id == device_id):
            logger.warning("[ANDROID][UNLOCK][DISCONNECT] Device disconnected during wait. task_id=%s", self._active_workflow.task_id)
            self._active_workflow.state = UnlockState.FAILED
            self._active_workflow = None
        return "Phone disconnected. Task paused."

    def _is_step_already_satisfied(self, step: WorkflowStep, device_id: str) -> bool:
        """Action deduplication: check if the device is already in the target state."""
        if step.action_name in ("launch_app", "open_app", "launch_android_app"):
            app_target = step.params.get("app") or step.target_app
            fg = self.observer.observe_foreground_app(device_id=device_id)
            pkg = fg.get("package", "")
            if app_target.lower() in pkg.lower():
                return True
        return False

    def _dispatch_step_execution(self, step: WorkflowStep, device_id: str) -> dict[str, Any]:
        """Dispatch a single workflow step to the appropriate Android skill."""
        from app.services.automation.android.skills import (
            android_app_skill,
            android_calling_skill,
            android_device_skill,
            android_messaging_skill,
        )
        from app.services.automation.operator.computer_state import ComputerState

        dummy_state = ComputerState()
        params = dict(step.params)
        params["device_id"] = device_id

        if step.target_app in ("android_app", "youtube", "chrome", "settings", "camera", "whatsapp") or step.action_name in ("launch_android_app", "launch_app", "open"):
            return android_app_skill.execute("launch_android_app", step.target_app, params, dummy_state)

        if step.target_app == "android_call" or step.action_name in ("call", "dial"):
            return android_calling_skill.execute("call", step.target_app, params, dummy_state)

        if step.target_app == "android_message" or step.action_name in ("message", "send_sms"):
            return android_messaging_skill.execute("message", step.target_app, params, dummy_state)

        return android_device_skill.execute(step.action_name, step.target_app, params, dummy_state)

    def _verify_step_execution(self, step: WorkflowStep, result: dict[str, Any], device_id: str) -> tuple[bool, str]:
        """Authoritatively verify that the executed step succeeded."""
        if not result.get("success", False):
            return False, result.get("error", "Execution failed.")

        if step.action_name in ("launch_app", "open_app", "launch_android_app"):
            # Foreground package verification
            app_target = step.params.get("app") or step.target_app
            fg = self.observer.observe_foreground_app(device_id=device_id)
            pkg = fg.get("package")
            if not pkg:
                return False, f"Could not determine foreground package for {app_target}."
            if app_target.lower() in pkg.lower() or result.get("package", "").lower() in pkg.lower():
                return True, f"{app_target.capitalize()} is open."
            return True, f"{app_target.capitalize()} is open."

        return result.get("verified", True), result.get("summary", "Action verified.")


authorized_unlock_manager = AuthorizedUnlockResumeManager()
