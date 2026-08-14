"""
FALSO 4.9 Adaptive Computer Operator Engine.

The central execution engine transforming FALSO into an Adaptive Computer Operator:
1. OBSERVE desktop state
2. RESOLVE pronouns and anaphoric references
3. PLAN with action idempotency
4. PERMISSION & scope verification (DENY-by-default)
5. SELECT safest reliable control method
6. EXECUTE physical actions against real Windows apps
7. VERIFY state changes authoritatively (NO FAKE SUCCESS)
8. UPDATE ComputerState & VerifiedActionHistory
9. RECOVER & REPLAN dynamically upon unexpected UI differences
10. INTERRUPT instantly on 'FALSO stop'
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from typing import Any

from app.services.automation.operator.action_selector import ControlMethod, action_selector
from app.services.automation.operator.computer_observer import computer_observer
from app.services.automation.operator.computer_state import (
    ComputerState,
    EvidenceType,
    StateValue,
    VerifiedActionRecord,
)
from app.services.automation.operator.pronoun_resolver import pronoun_resolver
from app.services.automation.operator.skills.skill_registry import skill_registry
from app.services.automation.permissions import PermissionLevel, RiskLevel, permission_manager
from app.services.automation.windows.executor import windows_executor
from app.services.automation.windows.window_manager import window_manager

logger = logging.getLogger(__name__)


class AdaptiveComputerOperator:
    """Master engine orchestrating adaptive computer operation."""

    def __init__(self) -> None:
        self.observer = computer_observer
        self.selector = action_selector
        self.resolver = pronoun_resolver
        self.skills = skill_registry
        self.executor = windows_executor
        self._current_state = ComputerState()
        self._is_active: bool = False
        self._is_cancelled: bool = False
        self._pending_confirmation: dict[str, Any] | None = None

    def is_active(self) -> bool:
        return self._is_active

    def cancel(self) -> str:
        """Immediately interrupt active computer operation."""
        self._is_cancelled = True
        self._is_active = False
        self._pending_confirmation = None
        # Cancel any pending Android unlock waits
        from app.services.automation.android.unlock_manager import authorized_unlock_manager
        authorized_unlock_manager.cancel_unlock_wait()
        logger.info("[OPERATOR] Interrupted by user cancellation.")
        return "Cancelled."

    async def run_operation(
        self,
        goal: str,
        task_id: str | None = None,
        session_id: str | None = None,
        session_history: list[Any] | None = None,
    ) -> str:
        """Main entry point for adaptive computer operation."""
        tid = task_id or str(uuid.uuid4())
        sid = session_id or "FALSO-SESSION-DEFAULT"
        self._is_active = True
        self._is_cancelled = False

        try:
            # 1. OBSERVE INITIAL STATE
            state = self.observer.observe()
            self._current_state = state

            # 2. RESOLVE PRONOUNS / REFERENCES
            resolved_goal, target_resolved, is_ambiguous = self.resolver.resolve_reference(
                goal, state, session_history=session_history
            )
            if is_ambiguous:
                self._is_active = False
                return "Which application or window would you like me to use?"

            # 3. MULTI-STEP TASK PARSING
            sub_goals = self._split_multi_step_goal(resolved_goal)

            last_output = "Done."
            for idx, step_goal in enumerate(sub_goals, 1):
                if self._is_cancelled:
                    return "Cancelled."

                step_res, step_out = await self._execute_single_step(
                    step_goal, tid, sid, state, is_last=(idx == len(sub_goals))
                )
                if not step_res:
                    self._is_active = False
                    return step_out or "I couldn't complete that."

                from app.services.automation.android.unlock_manager import authorized_unlock_manager, WorkflowStep, StepState
                active_wf = authorized_unlock_manager.get_active_workflow()
                if active_wf and active_wf.state.value == "WAITING_FOR_USER_UNLOCK":
                    # Append remaining sub-goals to pending steps if not already added
                    remaining_goals = sub_goals[idx:]
                    for rem in remaining_goals:
                        sel = self.selector.select_action(rem, state)
                        active_wf.pending_steps.append(
                            WorkflowStep(
                                action_id=str(uuid.uuid4())[:8],
                                action_name=sel.action_name,
                                target_app=sel.target_app,
                                params=sel.params,
                                state=StepState.PENDING,
                            )
                        )
                    self._is_active = False
                    return step_out

                last_output = step_out or last_output

            self._is_active = False
            return last_output

        except Exception as e:
            logger.error("[OPERATOR] Unexpected error in operator loop: %s", e, exc_info=True)
            self._is_active = False
            return "I couldn't complete that."

    async def _execute_single_step(
        self,
        step_goal: str,
        task_id: str,
        session_id: str,
        state: ComputerState,
        is_last: bool = True,
    ) -> tuple[bool, str]:
        """Execute and verify a single adaptive step."""
        # 1. OBSERVE
        state = self.observer.observe()
        self._current_state = state

        # 2. SELECT CONTROL METHOD
        selection = self.selector.select_action(step_goal, state)
        if selection.method == ControlMethod.UNAVAILABLE:
            return False, "I couldn't identify the target element."

        target_app = selection.target_app
        action_name = selection.action_name
        params = selection.params

        # 3. IDEMPOTENCY CHECK
        if self._is_step_idempotent(action_name, target_app, params, state):
            logger.info("[OPERATOR][IDEMPOTENCY] Action '%s' on '%s' already in desired state. Skipping redundant execution.", action_name, target_app)
            return True, "Done."

        # 4. PERMISSION CHECK
        allowed, reason, risk = self._check_permission(target_app, action_name, params)
        if not allowed:
            logger.warning("[OPERATOR][PERMISSION_DENIED] %s on %s: %s", action_name, target_app, reason)
            return False, f"Action blocked: {reason}"

        # 5. EXECUTION & RECOVERY LOOP (max 2 retries)
        verified = False
        reason_msg = "Done."
        max_retries = 2

        for attempt in range(max_retries + 1):
            if self._is_cancelled:
                return False, "Cancelled."

            before_state = self.observer.observe(target_hint=target_app)

            # Delegate to Application Skill if available
            skill = self.skills.find_skill(target_app, action_name)
            if skill:
                exec_result = skill.execute(action_name, target_app, params, before_state)
                # Small state settling delay
                time.sleep(0.3)
                after_state = self.observer.observe(target_hint=target_app)
                verified, reason_msg = skill.verify(action_name, target_app, before_state, after_state, exec_result)
            elif selection.method == ControlMethod.WINDOW_MANAGER:
                exec_result = self._execute_window_manager_action(action_name, target_app, params)
                time.sleep(0.3)
                after_state = self.observer.observe(target_hint=target_app)
                verified, reason_msg = self._verify_window_manager_action(action_name, target_app, before_state, after_state, exec_result)
            elif selection.method == ControlMethod.BROWSER_AUTOMATION:
                skill = self.skills.find_skill("Chrome", "navigate")
                exec_result = skill.execute("navigate", "Chrome", params, before_state) if skill else {"success": False}
                time.sleep(0.5)
                after_state = self.observer.observe(target_hint="Chrome")
                verified, reason_msg = (skill.verify("navigate", "Chrome", before_state, after_state, exec_result) if skill else (False, "No skill"))
            else:
                exec_result = {"success": False, "error": "No execution mechanism"}
                after_state = before_state
                verified = False
                reason_msg = "Failed."

            if verified:
                # 6. RECORD VERIFIED HISTORY & UPDATE STATE
                rec = VerifiedActionRecord(
                    task_id=task_id,
                    action_id=str(uuid.uuid4())[:8],
                    target=target_app,
                    action=action_name,
                    execution_result=exec_result,
                    verification_result=(verified, reason_msg),
                    safe_summary=f"{action_name} on {target_app}",
                )
                state.add_verified_action(rec)
                self._current_state = after_state

                # Return concise response
                concise_msg = self._format_concise_response(action_name, target_app, exec_result, reason_msg)
                return True, concise_msg

            # RECOVERY ATTEMPT
            logger.warning("[OPERATOR][VERIFY_FAIL] Attempt %d failed for %s on %s: %s", attempt + 1, action_name, target_app, reason_msg)
            if attempt < max_retries:
                # Attempt recovery: refocus target window before retrying (for desktop apps only)
                if selection.method != ControlMethod.ANDROID_SKILL and target_app and action_name not in ("open", "close", "close_window"):
                    window_manager.focus_window(target_app)
                    time.sleep(0.3)

        if selection.method == ControlMethod.ANDROID_SKILL and reason_msg and reason_msg != "Done.":
            return False, reason_msg
        return False, "I couldn't verify that action completed."

    def _is_step_idempotent(self, action: str, target: str, params: dict[str, Any], state: ComputerState) -> bool:
        """Check if action is already satisfied by current state."""
        if action in ("open", "open_app"):
            if state.is_app_open(target):
                # Bring to focus rather than launching duplicate
                window_manager.focus_window(target)
                return True
        if action in ("focus", "focus_window"):
            if state.is_app_foreground(target):
                return True
        if action == "navigate":
            url = params.get("url", "").lower()
            if state.browser.is_observed() and state.browser.value:
                curr = state.browser.value.current_url.lower()
                if url and url in curr:
                    return True
        return False

    def _check_permission(self, target: str, action: str, params: dict[str, Any]) -> tuple[bool, str, RiskLevel]:
        risk = permission_manager.get_risk_level(action, target, params)
        perm = permission_manager.check_capability(f"windows.{action}", target=target)
        return perm.allowed, perm.reason, risk

    def _execute_window_manager_action(self, action: str, target: str, params: dict[str, Any]) -> dict[str, Any]:
        from app.services.automation.windows.process_manager import process_manager
        if action in ("open", "open_app", "launch_app"):
            res = process_manager.launch_app(target)
            return res if isinstance(res, dict) else {"success": bool(res), "action": "open"}
        if action in ("close", "close_window"):
            ok = window_manager.close_window(target)
            return {"success": ok, "action": "close"}
        if action in ("focus", "focus_window"):
            ok = window_manager.focus_window(target)
            return {"success": ok, "action": "focus"}
        return {"success": False, "error": f"Unknown window action: {action}"}

    def _verify_window_manager_action(
        self,
        action: str,
        target: str,
        before_state: ComputerState,
        after_state: ComputerState,
        result: dict[str, Any],
    ) -> tuple[bool, str]:
        if not result.get("success", False):
            return False, result.get("error", "Window manager action failed.")
        if action in ("open", "open_app"):
            if after_state.is_app_open(target) and window_manager.verify_foreground(target):
                return True, f"{target} is open."
            return False, f"Failed to verify {target} is open and foregrounded."
        if action in ("close", "close_window"):
            if not window_manager.is_window_open(target):
                return True, f"{target} closed."
            return False, f"{target} window still present."
        if action in ("focus", "focus_window"):
            if window_manager.verify_foreground(target):
                return True, f"{target} focused."
            return False, f"Failed to focus {target}."
        return True, "Verified."

    def _format_concise_response(self, action: str, target: str, result: dict[str, Any], reason: str) -> str:
        # Cybersecurity diagnostic summary
        if target.lower() in ("security", "network", "diagnostics", "server", "port", "dns", "http", "logs") or action in ("diagnose", "port_check", "dns_check", "audit_logs"):
            return reason or result.get("summary") or "Diagnostic complete."
        # Android / Phone summaries
        if target.lower() in ("android_device", "android_app", "android_call", "android_message", "phone", "android") or action in ("launch_android_app", "unlock_phone", "wake_display", "ANDROID_UNLOCK_WAIT"):
            if result.get("waiting_for_unlock") or result.get("is_locked"):
                return result.get("summary") or result.get("prompt") or result.get("error") or "Your phone is locked. Unlock it and I'll continue."
            if result.get("requires_confirmation") and result.get("prompt"):
                return result.get("prompt")
            if not result.get("success", False) and result.get("error"):
                return result.get("error")
            return reason or result.get("summary") or "Done."
        # Calculator math response
        if target.lower() == "calculator" and action == "calculate":
            calc_val = result.get("actual_result", result.get("expected_result"))
            if calc_val is not None:
                return str(calc_val)
        if action == "new_tab":
            return "New tab opened."
        if action == "navigate":
            return reason or "Done."
        return "Done."

    def _split_multi_step_goal(self, goal: str) -> list[str]:
        """Decompose compound multi-step requests."""
        # Check for sequential delimiters: "then", "and then", comma + verb
        g_low = goal.lower()
        if " then " in g_low:
            return [p.strip() for p in re.split(r"\s+then\s+", goal, flags=re.IGNORECASE) if p.strip()]
        if " and then " in g_low:
            return [p.strip() for p in re.split(r"\s+and\s+then\s+", goal, flags=re.IGNORECASE) if p.strip()]
        if " and " in g_low:
            parts = [p.strip() for p in re.split(r"\s+and\s+", goal, flags=re.IGNORECASE) if p.strip()]
            action_verbs = ("open", "launch", "search", "calculate", "type", "click", "take", "check", "call", "message", "close", "focus", "wake", "unlock")
            if len(parts) >= 2 and any(parts[1].lower().startswith(v) for v in action_verbs):
                return parts
        # Single atomic goal
        return [goal.strip()]


operator_engine = AdaptiveComputerOperator()
