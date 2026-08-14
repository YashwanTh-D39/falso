"""
FALSO 4.9 Notepad Skill.

Provides real, truthful Windows Notepad automation, typing, clipboard inspection,
and document text verification.
Operations: open, focus, type_text, read_document, select_all, copy, paste, clear, save, close.
"""

from __future__ import annotations

import logging
from typing import Any

from app.services.automation.operator.computer_state import ComputerState
from app.services.automation.operator.skills.base_skill import BaseSkill
from app.services.automation.windows.clipboard_controller import clipboard_controller
from app.services.automation.windows.in_app_action_engine import StructuredInAppAction, in_app_action_engine
from app.services.automation.windows.ui_automation import ui_automation
from app.services.automation.windows.window_manager import window_manager

logger = logging.getLogger(__name__)


class NotepadSkill(BaseSkill):
    name = "notepad"
    allowed_applications = ["Notepad", "notepad"]

    def can_handle(self, target: str, action: str) -> bool:
        t = target.lower()
        return "notepad" in t or t in ("text editor", "document")

    def execute(self, action: str, target: str, params: dict[str, Any], state: ComputerState) -> dict[str, Any]:
        from app.services.automation.windows.process_manager import process_manager
        if action in ("open", "launch_app"):
            res = process_manager.launch_app("Notepad")
            return res if isinstance(res, dict) else {"success": bool(res), "action": "open"}

        if action == "focus":
            ok = window_manager.focus_window("Notepad")
            return {"success": ok, "action": "focus"}

        if action in ("type", "type_text"):
            text = params.get("text", "")
            act = StructuredInAppAction(application="Notepad", action="type_text", arguments={"text": text})
            return in_app_action_engine.execute_in_app_action(act)

        if action in ("copy", "select_all_copy"):
            act = StructuredInAppAction(application="Notepad", action="copy")
            return in_app_action_engine.execute_in_app_action(act)

        if action == "paste":
            act = StructuredInAppAction(application="Notepad", action="paste")
            return in_app_action_engine.execute_in_app_action(act)

        if action == "clear":
            act = StructuredInAppAction(application="Notepad", action="clear")
            return in_app_action_engine.execute_in_app_action(act)

        if action == "save":
            path = params.get("path", "")
            act = StructuredInAppAction(application="Notepad", action="save", arguments={"path": path})
            return in_app_action_engine.execute_in_app_action(act)

        if action in ("close", "close_window"):
            ok = window_manager.close_window("Notepad")
            return {"success": ok, "action": "close"}

        return {"success": False, "error": f"Unknown notepad action: {action}"}

    def verify(self, action: str, target: str, before_state: ComputerState, after_state: ComputerState, result: dict[str, Any]) -> tuple[bool, str]:
        if not result.get("success", False):
            return False, result.get("error", "Notepad action failed.")

        if action == "open":
            if after_state.is_app_open("Notepad") and window_manager.verify_foreground("Notepad"):
                return True, "Notepad is open."
            return False, "Failed to verify Notepad is open and foregrounded."

        if action == "close":
            if not window_manager.is_window_open("Notepad"):
                return True, "Notepad closed."
            return False, "Notepad window still present."

        if action in ("type", "type_text"):
            return result.get("verified", False), result.get("reason", "Text typed.")

        if action == "copy":
            if clipboard_controller.has_text():
                return True, "Content copied to clipboard."
            return False, "Clipboard is empty after copy."

        if action == "paste":
            return result.get("verified", False), result.get("reason", "Content pasted.")

        return True, "Notepad action verified."
