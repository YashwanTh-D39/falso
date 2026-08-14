"""
In-App Action Automation Engine for FALSO 4.5.

Executes structured in-app actions against approved applications with
pre/post state observation, explicit verification, failure recovery,
and permission enforcement.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from app.services.automation.permissions import permission_manager, RiskLevel
from app.services.automation.windows.app_registry import app_registry
from app.services.automation.windows.app_action_registry import app_action_registry, StructuredInAppAction
from app.services.automation.windows.window_manager import window_manager
from app.services.automation.windows.process_manager import process_manager

logger = logging.getLogger(__name__)


class InAppActionEngine:
    """Permission-controlled In-App Action Automation Engine."""

    def execute_in_app_action(
        self,
        action: StructuredInAppAction | dict[str, Any],
        task_id: str = "IN-APP-TASK",
        request_id: str = "IN-APP-REQ",
    ) -> dict[str, Any]:
        """Execute structured in-app action with state observation and verification."""
        if isinstance(action, dict):
            struct_action = StructuredInAppAction(
                application=action.get("application", "Calculator"),
                action=action.get("action", "calculate"),
                arguments=action.get("arguments", {}),
                capability=action.get("capability", "windows.interact_with_app"),
                risk_level=action.get("risk_level", RiskLevel.MEDIUM),
                description=action.get("description", ""),
            )
        else:
            struct_action = action

        app_name = struct_action.application
        act_name = struct_action.action

        # Resolve app identity
        app_identity = app_registry.resolve(app_name)
        canonical = app_identity.canonical_name if app_identity else app_name

        # ── 1. PERMISSION CHECKS ──
        if permission_manager.is_lockdown_active():
            return {
                "success": False,
                "action": act_name,
                "target": canonical,
                "executed": False,
                "verified": False,
                "verification_reason": "FALSO Emergency Lockdown Active: In-app automation disabled.",
                "error": "Emergency Lockdown Active",
            }

        app_perm = permission_manager.check_application_launch(canonical.lower())
        if not app_perm.allowed:
            logger.warning("[IN_APP_ENGINE] Launch/Interaction DENIED for '%s': %s", canonical, app_perm.reason)
            return {
                "success": False,
                "action": act_name,
                "target": canonical,
                "executed": False,
                "verified": False,
                "verification_reason": app_perm.reason,
                "error": app_perm.reason,
            }

        # Retrieve action definition from registry
        defn = app_action_registry.get_action(canonical, act_name)
        if not defn:
            error_msg = f"Action '{act_name}' is not registered for application '{canonical}'."
            logger.warning("[IN_APP_ENGINE] %s", error_msg)
            return {
                "success": False,
                "action": act_name,
                "target": canonical,
                "executed": False,
                "verified": False,
                "verification_reason": error_msg,
                "error": error_msg,
            }

        start_time = time.perf_counter()
        before_state = {
            "window_open": window_manager.is_window_open(canonical),
            "timestamp": time.time(),
        }

        # ── 2. PRECONDITION: ENSURE WINDOW OPEN & FOCUSED ──
        if not before_state["window_open"]:
            launched = process_manager.launch_app(canonical)
            if not launched["success"]:
                return {
                    "success": False,
                    "action": act_name,
                    "target": canonical,
                    "executed": False,
                    "verified": False,
                    "verification_reason": f"Failed to launch {canonical}.",
                    "error": f"Failed to launch {canonical}",
                }
            time.sleep(0.3)

        window_manager.focus_window(canonical)

        # ── 3. EXECUTE ACTION HANDLER ──
        try:
            handler_result = defn.handler(struct_action)
            executed = True
            after_state = {
                "window_open": window_manager.is_window_open(canonical),
                "handler_result": handler_result,
                "timestamp": time.time(),
            }
            if isinstance(handler_result, dict):
                after_state.update(handler_result)

            # ── 4. VERIFY ACTION ──
            verified, reason = defn.verification_handler(before_state, after_state)
            duration = (time.perf_counter() - start_time) * 1000.0

            permission_manager.log_action(
                task_id=task_id,
                request_id=request_id,
                action_id=f"in_app.{act_name}",
                capability=defn.capability,
                target=canonical,
                result="SUCCESS" if verified else "FAILED",
                duration_ms=duration,
            )

            res_val = handler_result.get("result") if isinstance(handler_result, dict) else None

            return {
                "success": verified,
                "action": act_name,
                "target": canonical,
                "executed": executed,
                "verified": verified,
                "verification_reason": reason,
                "before_state": before_state,
                "after_state": after_state,
                "result": res_val,
                "duration_ms": duration,
            }

        except Exception as e:
            logger.exception("[IN_APP_ENGINE] Error executing action '%s' on '%s': %s", act_name, canonical, e)
            duration = (time.perf_counter() - start_time) * 1000.0
            return {
                "success": False,
                "action": act_name,
                "target": canonical,
                "executed": False,
                "verified": False,
                "verification_reason": f"I couldn't complete {act_name} in {canonical}.",
                "error": str(e),
                "duration_ms": duration,
            }


in_app_action_engine = InAppActionEngine()
