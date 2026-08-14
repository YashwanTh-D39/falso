"""
FALSO 4.9 Chrome / Browser Skill.

Provides real, truthful Chrome browser automation, tab management, navigation,
and web page state verification.
Operations: open, focus, new_tab, close_tab, navigate, search, back, forward, refresh, close.
"""

from __future__ import annotations

import logging
from typing import Any

from app.services.automation.browser.browser_engine import browser_engine
from app.services.automation.operator.computer_state import ComputerState
from app.services.automation.operator.skills.base_skill import BaseSkill
from app.services.automation.windows.browser_controller import browser_controller
from app.services.automation.windows.in_app_action_engine import StructuredInAppAction, in_app_action_engine
from app.services.automation.windows.window_manager import window_manager

logger = logging.getLogger(__name__)


class ChromeSkill(BaseSkill):
    name = "chrome"
    allowed_applications = ["Chrome", "chrome", "Google Chrome", "browser"]

    def can_handle(self, target: str, action: str) -> bool:
        t = target.lower()
        return "chrome" in t or "browser" in t or "web" in t

    def execute(self, action: str, target: str, params: dict[str, Any], state: ComputerState) -> dict[str, Any]:
        if action == "open":
            res = browser_controller.open_browser()
            return res

        if action == "focus":
            ok = window_manager.focus_window("Chrome")
            return {"success": ok, "action": "focus"}

        if action == "new_tab":
            act = StructuredInAppAction(application="Chrome", action="new_tab")
            return in_app_action_engine.execute_in_app_action(act)

        if action == "close_tab":
            act = StructuredInAppAction(application="Chrome", action="close_tab")
            return in_app_action_engine.execute_in_app_action(act)

        if action == "navigate":
            url = params.get("url", "https://google.com")
            act = StructuredInAppAction(application="Chrome", action="navigate", arguments={"url": url})
            return in_app_action_engine.execute_in_app_action(act)

        if action == "search":
            query = params.get("query", "")
            url = f"https://google.com/search?q={query}"
            act = StructuredInAppAction(application="Chrome", action="navigate", arguments={"url": url})
            return in_app_action_engine.execute_in_app_action(act)

        if action == "back":
            act = StructuredInAppAction(application="Chrome", action="back")
            return in_app_action_engine.execute_in_app_action(act)

        if action == "forward":
            act = StructuredInAppAction(application="Chrome", action="forward")
            return in_app_action_engine.execute_in_app_action(act)

        if action == "refresh":
            act = StructuredInAppAction(application="Chrome", action="refresh")
            return in_app_action_engine.execute_in_app_action(act)

        if action == "close":
            ok = window_manager.close_window("Chrome")
            return {"success": ok, "action": "close"}

        return {"success": False, "error": f"Unknown chrome action: {action}"}

    def verify(self, action: str, target: str, before_state: ComputerState, after_state: ComputerState, result: dict[str, Any]) -> tuple[bool, str]:
        if not result.get("success", False):
            return False, result.get("error", "Chrome action failed.")

        if action == "open":
            if after_state.is_app_open("Chrome") and window_manager.verify_foreground("Chrome"):
                return True, "Chrome is open."
            return False, "Failed to verify Chrome is open and foregrounded."

        if action == "close":
            if not window_manager.is_window_open("Chrome"):
                return True, "Chrome closed."
            return False, "Chrome window still present."

        if action in ("new_tab", "close_tab", "navigate", "search", "back", "forward", "refresh"):
            return result.get("verified", False), result.get("reason", "Chrome action completed.")

        return True, "Chrome action verified."
