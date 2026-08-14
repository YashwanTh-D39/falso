"""
TEST SUITE: REAL WINDOWS VERIFICATION & TRUTHFUL AUTOMATION CONTRACTS

Validates:
1. Background process != visible window (is_window_open returns False when no visible HWND)
2. Focus verification (focus_window fails without HWND, verify_foreground checks active HWND)
3. Wrong-target protection (input refused if intended target is not foreground)
4. Unknown key rejection (_get_vk returns 0, never silently sends SPACE)
5. Fake UI click rejection (click_element returns False on non-existent element, never fake True)
6. Calculator verification (UI Automation reads actual display, requires exact numerical match)
7. Chrome new-tab verification (requires foreground and tab/address bar verification)
8. Chrome close-tab verification (requires verified tab closure)
9. Notepad typing verification (UI Automation reads actual document text, not title asterisk)
10. Copy/paste verification (clipboard_controller get/set/clear/has_text, zero logging of content)
11. Executor success != verified success (executed=True, verified=False yields success=False)
12. Verification failure != completion (unverified step causes RECOVERING and failure, never COMPLETED)
"""

from unittest.mock import MagicMock, patch
import pytest

from app.services.automation.autopilot import AutopilotAgent, OperatingMode, TaskStatus
from app.services.automation.permissions import permission_manager
from app.services.automation.windows.app_action_registry import app_action_registry
from app.services.automation.windows.clipboard_controller import clipboard_controller
from app.services.automation.windows.executor import windows_executor
from app.services.automation.windows.keyboard_controller import keyboard_controller
from app.services.automation.windows.process_manager import process_manager
from app.services.automation.windows.ui_automation import ui_automation
from app.services.automation.windows.window_manager import window_manager


class TestRealWindowsVerification:

    def setup_method(self):
        permission_manager.disable_lockdown()

    # 1. Background process != visible window
    def test_01_background_process_is_not_visible_window(self):
        with patch.object(window_manager, "list_windows", return_value=[]), \
             patch.object(process_manager, "is_process_running", return_value=True):
            # Process is running in background, but no visible HWND exists
            is_open = window_manager.is_window_open("Calculator")
            assert is_open is False, "is_window_open must return False when no visible HWND exists"

    # 2. Focus verification
    def test_02_focus_verification_requires_real_hwnd(self):
        with patch.object(window_manager, "list_windows", return_value=[]):
            focused = window_manager.focus_window("Calculator")
            assert focused is False, "focus_window must return False when target window has no HWND"

        with patch.object(window_manager, "get_foreground_hwnd", return_value={"hwnd": 12345, "title": "Calculator", "process_id": 999}):
            assert window_manager.verify_foreground("Calculator") is True
            assert window_manager.verify_foreground("Notepad") is False

    # 3. Wrong-target protection
    def test_03_wrong_target_protection_blocks_input(self):
        # Target app window exists, focus was attempted, but another window (Notepad) held foreground
        with patch.object(window_manager, "is_window_open", return_value=True), \
             patch.object(window_manager, "focus_window", return_value=True), \
             patch.object(window_manager, "verify_foreground", return_value=False), \
             patch.object(window_manager, "get_foreground_hwnd", return_value={"hwnd": 111, "title": "Untitled - Notepad", "process_id": 100}):
            res = windows_executor.execute_action(
                "interact_with_app",
                app="Chrome",
                action="new_tab",
                task_id="TEST-GUARD-01",
            )
            assert res["success"] is False
            assert res["verified"] is False
            assert "foreground" in res.get("verification_reason", "").lower() or "not" in res.get("verification_reason", "").lower()

    # 4. Unknown key rejection
    def test_04_unknown_key_rejection_returns_zero(self):
        vk = keyboard_controller._get_vk("INVALID_NONEXISTENT_KEY_XYZ")
        assert vk == 0, f"Unknown key must return 0, but returned {vk} (0x{vk:02x})"
        assert vk != 0x20, "Unknown key must NEVER default to 0x20 (SPACE)"

        # Hotkey with unknown key fails
        executed = keyboard_controller.send_hotkey(["INVALID_KEY_NAME_ABC"])
        assert executed is False

    # 5. Fake UI click rejection
    def test_05_fake_ui_click_rejection(self):
        # If element is not found, click_element returns False, never True
        with patch.object(ui_automation, "find_element", return_value=None):
            clicked = ui_automation.click_element("NonexistentButton12345", role="button")
            assert clicked is False, "click_element must return False if element does not exist"

    # 6. Calculator verification
    def test_06_calculator_verification_checks_actual_display(self):
        defn = app_action_registry.get_action("calculator", "add")
        assert defn is not None

        # Case A: Display matches expected 20 -> PASS
        with patch.object(window_manager, "verify_foreground", return_value=True), \
             patch.object(ui_automation, "is_available", return_value=True), \
             patch.object(ui_automation, "get_element_text", return_value="Display is 20"):
            verified, reason = defn.verification_handler({}, {"expected_result": 20})
            assert verified is True
            assert "20" in reason

        # Case B: Display does not match (e.g. shows 0 or wrong value) -> FAIL
        with patch.object(window_manager, "verify_foreground", return_value=True), \
             patch.object(ui_automation, "is_available", return_value=True), \
             patch.object(ui_automation, "get_element_text", return_value="Display is 0"):
            verified_wrong, reason_wrong = defn.verification_handler({}, {"expected_result": 20})
            assert verified_wrong is False

    # 7. Chrome new-tab verification
    def test_07_chrome_new_tab_verification(self):
        defn = app_action_registry.get_action("chrome", "new_tab")
        assert defn is not None

        # When foreground is Chrome with New Tab -> PASS
        with patch.object(window_manager, "get_foreground_hwnd", return_value={"hwnd": 200, "title": "New Tab - Google Chrome", "process_id": 500}), \
             patch.object(window_manager, "verify_foreground", return_value=True):
            verified, reason = defn.verification_handler({}, {"post_title": "New Tab - Google Chrome"})
            assert verified is True

        # When foreground is something else -> FAIL
        with patch.object(window_manager, "get_foreground_hwnd", return_value={"hwnd": 200, "title": "Calculator", "process_id": 500}), \
             patch.object(window_manager, "verify_foreground", return_value=False):
            verified_fail, reason_fail = defn.verification_handler({}, {})
            assert verified_fail is False

    # 8. Chrome close-tab verification
    def test_08_chrome_close_tab_verification(self):
        defn = app_action_registry.get_action("chrome", "close_tab")
        assert defn is not None

        # Title changed (adjacent tab active) -> PASS
        with patch.object(window_manager, "verify_foreground", return_value=True):
            verified, reason = defn.verification_handler({}, {"pre_title": "Google", "post_title": "New Tab - Google Chrome"})
            assert verified is True

        # Chrome closed entirely (was last tab) -> PASS
        with patch.object(window_manager, "verify_foreground", return_value=False):
            verified, reason = defn.verification_handler({}, {"chrome_still_open": False})
            assert verified is True

        # Chrome lost foreground -> FAIL
        with patch.object(window_manager, "verify_foreground", return_value=False):
            verified_fail, reason_fail = defn.verification_handler({}, {"pre_title": "Google", "post_title": "Google", "chrome_still_open": True})
            assert verified_fail is False

    # 9. Notepad typing verification
    def test_09_notepad_typing_verification_checks_document_content(self):
        defn = app_action_registry.get_action("notepad", "type")
        assert defn is not None

        # UIA finds document text contains typed string -> PASS
        with patch.object(window_manager, "verify_foreground", return_value=True), \
             patch.object(ui_automation, "is_available", return_value=True), \
             patch.object(ui_automation, "get_element_value", return_value="hello FALSO\n"):
            verified, reason = defn.verification_handler({}, {"typed_text": "hello FALSO"})
            assert verified is True

        # Document is empty -> FAIL (even if title has asterisk)
        with patch.object(window_manager, "verify_foreground", return_value=True), \
             patch.object(ui_automation, "is_available", return_value=True), \
             patch.object(ui_automation, "get_element_value", return_value=""):
            verified_fail, reason_fail = defn.verification_handler({}, {"typed_text": "hello FALSO"})
            assert verified_fail is False

    # 10. Copy/paste verification
    def test_10_clipboard_controller_contracts(self):
        # Set text, has_text, get_text, clear
        clipboard_controller.set_text("TEST_STRING_INTEGRITY")
        assert clipboard_controller.has_text() is True
        text = clipboard_controller.get_text()
        assert text == "TEST_STRING_INTEGRITY"

        clipboard_controller.clear()
        assert clipboard_controller.has_text() is False

    # 11. Executor success != verified success
    def test_11_executor_dispatched_without_verified_is_failure(self):
        with patch.object(keyboard_controller, "type_text", return_value=True), \
             patch.object(window_manager, "get_foreground_hwnd", return_value={"hwnd": 0, "title": "", "process_id": 0}):
            res = windows_executor.execute_action("type_text", text="hello")
            assert res["dispatched"] is True
            assert res["executed"] is False
            assert res["verified"] is False
            assert res["success"] is False

    # 12. Verification failure != completion
    @pytest.mark.asyncio
    async def test_12_verification_failure_never_marks_completed(self):
        agent = AutopilotAgent()
        with patch.object(
            windows_executor,
            "execute_action",
            return_value={
                "success": False,
                "dispatched": True,
                "executed": True,
                "verified": False,
                "verification_reason": "Display did not show expected result 20.",
            },
        ), patch.object(window_manager, "is_window_open", return_value=True):
            res = await agent.run_goal("Add 10 + 10 in Calculator.", task_id="TEST-VERIF-12")
            assert res != "Done."
            assert res != "20."
            assert agent.completed_tasks[-1].status == TaskStatus.FAILED
            assert agent.completed_tasks[-1].status != TaskStatus.COMPLETED
