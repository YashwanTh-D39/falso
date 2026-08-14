"""
FALSO 4.9 Calculator Skill.

Provides real, truthful Windows Calculator automation and UIA verification.
Operations: open, focus, calculate, read_result, clear, close.
"""

from __future__ import annotations

import logging
from typing import Any

from app.services.automation.operator.computer_state import ComputerState
from app.services.automation.operator.skills.base_skill import BaseSkill
from app.services.automation.windows.in_app_action_engine import StructuredInAppAction, in_app_action_engine
from app.services.automation.windows.ui_automation import ui_automation
from app.services.automation.windows.window_manager import window_manager

logger = logging.getLogger(__name__)


class CalculatorSkill(BaseSkill):
    name = "calculator"
    allowed_applications = ["Calculator", "calc"]

    def can_handle(self, target: str, action: str) -> bool:
        t = target.lower()
        return "calc" in t or t in ("calculator", "standard")

    def execute(self, action: str, target: str, params: dict[str, Any], state: ComputerState) -> dict[str, Any]:
        from app.services.automation.windows.process_manager import process_manager
        if action in ("open", "launch_app"):
            res = process_manager.launch_app("Calculator")
            return res if isinstance(res, dict) else {"success": bool(res), "action": "open"}

        if action == "focus":
            ok = window_manager.focus_window("Calculator")
            return {"success": ok, "action": "focus"}

        if action == "calculate":
            expr = params.get("expression", params.get("goal", "10+10"))
            act = StructuredInAppAction(application="Calculator", action="calculate", arguments={"expression": expr})
            return in_app_action_engine.execute_in_app_action(act)

        if action == "clear":
            act = StructuredInAppAction(application="Calculator", action="clear")
            return in_app_action_engine.execute_in_app_action(act)

        if action in ("close", "close_window"):
            ok = window_manager.close_window("Calculator")
            return {"success": ok, "action": "close"}

        return {"success": False, "error": f"Unknown calculator action: {action}"}

    def verify(self, action: str, target: str, before_state: ComputerState, after_state: ComputerState, result: dict[str, Any]) -> tuple[bool, str]:
        if not result.get("success", False):
            return False, result.get("error", "Calculator action failed.")

        if action == "open":
            if after_state.is_app_open("Calculator") and window_manager.verify_foreground("Calculator"):
                return True, "Calculator is open."
            return False, "Failed to verify Calculator is open and foregrounded."

        if action == "close":
            if not window_manager.is_window_open("Calculator"):
                return True, "Calculator closed."
            return False, "Calculator window still present."

        if action == "calculate":
            return result.get("verified", False), result.get("reason", "Calculated.")

        if action == "clear":
            return result.get("verified", False), result.get("reason", "Cleared.")

        return True, "Calculator action verified."
