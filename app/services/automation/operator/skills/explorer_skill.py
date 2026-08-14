"""
FALSO 4.9 File Explorer Skill.

Provides real, truthful Windows File Explorer automation and verification.
Operations: open_folder, focus, navigate, back, refresh, close.
"""

from __future__ import annotations

import logging
from typing import Any

from app.services.automation.operator.computer_state import ComputerState
from app.services.automation.operator.skills.base_skill import BaseSkill
from app.services.automation.windows.in_app_action_engine import StructuredInAppAction, in_app_action_engine
from app.services.automation.windows.window_manager import window_manager

logger = logging.getLogger(__name__)


class ExplorerSkill(BaseSkill):
    name = "explorer"
    allowed_applications = ["Explorer", "explorer", "File Explorer"]

    def can_handle(self, target: str, action: str) -> bool:
        t = target.lower()
        return "explorer" in t or "folder" in t or "directory" in t or "files" in t

    def execute(self, action: str, target: str, params: dict[str, Any], state: ComputerState) -> dict[str, Any]:
        from app.services.automation.windows.process_manager import process_manager
        if action in ("open", "open_folder", "launch_app"):
            folder = params.get("folder", params.get("path", ""))
            res = process_manager.launch_app("Explorer", args=folder if folder else None)
            return res if isinstance(res, dict) else {"success": bool(res), "action": "open"}

        if action == "focus":
            ok = window_manager.focus_window("Explorer")
            return {"success": ok, "action": "focus"}

        if action in ("navigate", "navigate_folder"):
            folder = params.get("folder", params.get("path", ""))
            act = StructuredInAppAction(application="Explorer", action="navigate_folder", arguments={"folder": folder})
            return in_app_action_engine.execute_in_app_action(act)

        if action == "back":
            act = StructuredInAppAction(application="Explorer", action="back")
            return in_app_action_engine.execute_in_app_action(act)

        if action == "refresh":
            act = StructuredInAppAction(application="Explorer", action="refresh")
            return in_app_action_engine.execute_in_app_action(act)

        if action == "close":
            ok = window_manager.close_window("Explorer")
            return {"success": ok, "action": "close"}

        return {"success": False, "error": f"Unknown explorer action: {action}"}

    def verify(self, action: str, target: str, before_state: ComputerState, after_state: ComputerState, result: dict[str, Any]) -> tuple[bool, str]:
        if not result.get("success", False):
            return False, result.get("error", "Explorer action failed.")

        if action in ("open", "open_folder"):
            if after_state.is_app_open("Explorer") and window_manager.verify_foreground("Explorer"):
                return True, "File Explorer is open."
            return False, "Failed to verify File Explorer is open and foregrounded."

        if action == "close":
            if not window_manager.is_window_open("Explorer"):
                return True, "File Explorer closed."
            return False, "File Explorer window still present."

        if action in ("navigate", "navigate_folder", "back", "refresh"):
            return result.get("verified", False), result.get("reason", "Explorer action completed.")

        return True, "Explorer action verified."
