"""
Unit tests for FALSO 4.5 In-App Action Automation Engine.
"""

import asyncio
import os
import pytest
from unittest.mock import patch, MagicMock

from app.services.automation.windows.app_action_registry import app_action_registry, StructuredInAppAction
from app.services.automation.windows.in_app_action_engine import in_app_action_engine
from app.services.automation.windows.executor import windows_executor
from app.services.automation.windows.window_manager import window_manager
from app.services.automation.windows.process_manager import process_manager
from app.services.automation.windows.browser_controller import browser_controller
from app.services.automation.permissions import permission_manager
from app.services.automation.goal_planner import goal_planner
from app.services.session_history import session_history_manager
from app.services.brain import BrainService


class TestFalso45InAppActions:

    def setup_method(self):
        permission_manager.disable_lockdown()
        session_history_manager.clear_session("TEST-INAPP-SESSION")

    def teardown_method(self):
        permission_manager.disable_lockdown()

    # ── CALCULATOR ──

    def test_01_open_calculator(self):
        with patch.object(window_manager, "is_window_open", return_value=True):
            res = windows_executor.execute_action("launch_app", target="Calculator")
            assert res["success"] is True

    def test_02_calculate_10_plus_10(self):
        with patch.object(window_manager, "is_window_open", return_value=True), \
             patch.object(window_manager, "focus_window", return_value=True), \
             patch.object(window_manager, "verify_foreground", return_value=True):
            act = StructuredInAppAction(application="Calculator", action="calculate", arguments={"expression": "10 + 10"})
            res = in_app_action_engine.execute_in_app_action(act)
            assert res["success"] is True
            assert res["result"] == 20

    def test_03_verify_20(self):
        with patch.object(window_manager, "is_window_open", return_value=True), \
             patch.object(window_manager, "focus_window", return_value=True), \
             patch.object(window_manager, "verify_foreground", return_value=True):
            act = StructuredInAppAction(application="Calculator", action="calculate", arguments={"expression": "10 + 10"})
            res = in_app_action_engine.execute_in_app_action(act)
            assert res["verified"] is True
            assert "20" in res["verification_reason"]

    def test_04_calculate_25_times_4(self):
        with patch.object(window_manager, "is_window_open", return_value=True), \
             patch.object(window_manager, "focus_window", return_value=True), \
             patch.object(window_manager, "verify_foreground", return_value=True):
            act = StructuredInAppAction(application="Calculator", action="calculate", arguments={"expression": "25 * 4"})
            res = in_app_action_engine.execute_in_app_action(act)
            assert res["success"] is True
            assert res["result"] == 100

    def test_05_clear_calculator(self):
        with patch.object(window_manager, "is_window_open", return_value=True), \
             patch.object(window_manager, "focus_window", return_value=True), \
             patch.object(window_manager, "verify_foreground", return_value=True):
            act = StructuredInAppAction(application="Calculator", action="calculate", arguments={"expression": "0"})
            res = in_app_action_engine.execute_in_app_action(act)
            assert res["success"] is True

    def test_06_close_calculator(self):
        with patch.object(window_manager, "list_windows", return_value=[{"hwnd": 1, "title": "Calculator"}]), \
             patch.object(window_manager, "wait_for_window_close", return_value=True), \
             patch.object(process_manager, "is_process_running", return_value=False):
            res = window_manager.close_window("Calculator")
            assert res["verified"] is True

    # ── CHROME ──

    def test_07_open_chrome(self):
        with patch.object(window_manager, "is_window_open", return_value=True):
            res = windows_executor.execute_action("launch_app", target="Chrome")
            assert res["success"] is True

    def test_08_new_tab_chrome(self):
        with patch.object(window_manager, "is_window_open", return_value=True), \
             patch.object(window_manager, "focus_window", return_value=True), \
             patch.object(window_manager, "verify_foreground", return_value=True):
            act = StructuredInAppAction(application="Chrome", action="new_tab")
            res = in_app_action_engine.execute_in_app_action(act)
            assert res["success"] is True

    def test_09_verify_new_tab(self):
        with patch.object(window_manager, "is_window_open", return_value=True), \
             patch.object(window_manager, "focus_window", return_value=True), \
             patch.object(window_manager, "verify_foreground", return_value=True):
            act = StructuredInAppAction(application="Chrome", action="new_tab")
            res = in_app_action_engine.execute_in_app_action(act)
            assert res["verified"] is True
            assert res["verification_reason"] == "New tab opened."

    def test_10_close_tab_chrome(self):
        with patch.object(window_manager, "is_window_open", return_value=True), \
             patch.object(window_manager, "focus_window", return_value=True), \
             patch.object(window_manager, "verify_foreground", return_value=True):
            act = StructuredInAppAction(application="Chrome", action="close_tab")
            res = in_app_action_engine.execute_in_app_action(act)
            assert res["success"] is True

    def test_11_navigate_to_approved_url(self):
        with patch.object(window_manager, "is_window_open", return_value=True), \
             patch.object(window_manager, "focus_window", return_value=True), \
             patch.object(window_manager, "verify_foreground", return_value=True):
            act = StructuredInAppAction(application="Chrome", action="navigate", arguments={"url": "https://www.google.com"})
            res = in_app_action_engine.execute_in_app_action(act)
            assert res["success"] is True

    def test_12_verify_navigation(self):
        with patch.object(window_manager, "is_window_open", return_value=True), \
             patch.object(window_manager, "focus_window", return_value=True), \
             patch.object(window_manager, "verify_foreground", return_value=True):
            act = StructuredInAppAction(application="Chrome", action="navigate", arguments={"url": "https://example.com"})
            res = in_app_action_engine.execute_in_app_action(act)
            assert res["verified"] is True
            assert "https://example.com" in res["verification_reason"]

    def test_13_chrome_back(self):
        with patch.object(window_manager, "is_window_open", return_value=True):
            act = app_action_registry.resolve_natural_language_action("Chrome", "back")
            assert act is not None
            assert act.action == "back"

    def test_14_chrome_forward(self):
        with patch.object(window_manager, "is_window_open", return_value=True):
            act = app_action_registry.resolve_natural_language_action("Chrome", "forward")
            assert act is not None
            assert act.action == "forward"

    def test_15_chrome_refresh(self):
        with patch.object(window_manager, "is_window_open", return_value=True):
            act = app_action_registry.resolve_natural_language_action("Chrome", "refresh")
            assert act is not None
            assert act.action == "refresh"

    # ── NOTEPAD ──

    def test_16_open_notepad(self):
        with patch.object(window_manager, "is_window_open", return_value=True):
            res = windows_executor.execute_action("launch_app", target="Notepad")
            assert res["success"] is True

    def test_17_type_text_notepad(self):
        with patch.object(window_manager, "is_window_open", return_value=True), \
             patch.object(window_manager, "focus_window", return_value=True), \
             patch.object(window_manager, "verify_foreground", return_value=True):
            act = StructuredInAppAction(application="Notepad", action="type", arguments={"text": "hello FALSO"})
            res = in_app_action_engine.execute_in_app_action(act)
            assert res["success"] is True

    def test_18_verify_text_notepad(self):
        with patch.object(window_manager, "is_window_open", return_value=True), \
             patch.object(window_manager, "focus_window", return_value=True), \
             patch.object(window_manager, "verify_foreground", return_value=True):
            act = StructuredInAppAction(application="Notepad", action="type", arguments={"text": "hello FALSO"})
            res = in_app_action_engine.execute_in_app_action(act)
            assert res["verified"] is True
            assert "hello FALSO" in res["verification_reason"]

    def test_19_save_explicit_user_path(self):
        with patch.object(window_manager, "is_window_open", return_value=True), \
             patch.object(window_manager, "focus_window", return_value=True), \
             patch.object(window_manager, "verify_foreground", return_value=True):
            act = StructuredInAppAction(application="Notepad", action="save", arguments={"path": r"C:\Users\Admin\Project-Falso\test.txt"})
            res = in_app_action_engine.execute_in_app_action(act)
            assert res["success"] is True

    def test_20_close_notepad(self):
        with patch.object(window_manager, "list_windows", return_value=[{"hwnd": 2, "title": "Notepad"}]), \
             patch.object(window_manager, "wait_for_window_close", return_value=True), \
             patch.object(process_manager, "is_process_running", return_value=False):
            res = window_manager.close_window("Notepad")
            assert res["verified"] is True

    # ── FILE EXPLORER ──

    def test_21_open_explorer(self):
        with patch.object(window_manager, "is_window_open", return_value=True), \
             patch.object(window_manager, "wait_for_window", return_value=True):
            res = windows_executor.execute_action("open_approved_folder", target=r"C:\Users\Admin\Project-Falso")
            assert res["success"] is True

    def test_22_navigate_approved_folder(self):
        with patch.object(window_manager, "is_window_open", return_value=True):
            act = StructuredInAppAction(application="File Explorer", action="open_folder", arguments={"path": r"C:\Users\Admin\Project-Falso"})
            res = in_app_action_engine.execute_in_app_action(act)
            assert res["success"] is True

    def test_23_explorer_back(self):
        act = app_action_registry.resolve_natural_language_action("File Explorer", "back")
        assert act is not None
        assert act.action == "back"

    def test_24_explorer_refresh(self):
        act = app_action_registry.resolve_natural_language_action("File Explorer", "refresh")
        assert act is not None
        assert act.action == "refresh"

    def test_25_close_explorer(self):
        with patch.object(window_manager, "list_windows", return_value=[{"hwnd": 3, "title": "File Explorer"}]), \
             patch.object(window_manager, "wait_for_window_close", return_value=True), \
             patch.object(process_manager, "is_process_running", return_value=False):
            res = window_manager.close_window("File Explorer")
            assert res["verified"] is True

    # ── SECURITY BOUNDARIES ──

    def test_26_arbitrary_shell_denied(self):
        perm = permission_manager.check_command_execution("cmd.exe /c rd /s /q C:\\")
        assert perm.allowed is False

    def test_27_arbitrary_powershell_denied(self):
        perm = permission_manager.check_command_execution("powershell.exe -Command Get-Process")
        assert perm.allowed is False

    def test_28_protected_filesystem_denied(self):
        perm = permission_manager.check_filesystem_access(r"C:\Windows\System32\config")
        assert perm.allowed is False

    def test_29_arbitrary_process_control_denied(self):
        assert process_manager.stop_process("svchost") is False

    def test_30_env_access_denied(self):
        perm = permission_manager.check_filesystem_access(r"C:\Users\Admin\Project-Falso\.env")
        assert perm.allowed is False

    # ── MEMORY & MULTI-ACTION ──

    def test_31_open_chrome_then_open_new_tab(self):
        plan1 = goal_planner.create_plan("Open Chrome", session_id="TEST-INAPP-SESSION")
        assert plan1.steps[0].target.lower() == "chrome"
        session_history_manager.append_assistant_message("TEST-INAPP-SESSION", "Chrome is open.")
        last_app = session_history_manager.get_last_target_app("TEST-INAPP-SESSION")
        assert last_app == "Chrome"

    def test_32_open_calculator_then_calculate_10_plus_10(self):
        plan = goal_planner.create_plan("Add 10 + 10", session_id="TEST-INAPP-SESSION")
        assert len(plan.steps) >= 1
        assert plan.steps[-1].action in ("interact_with_app", "calculate")

    def test_33_multi_step_action(self):
        plan = goal_planner.create_plan("Open Chrome, create a new tab, go to google.com", session_id="TEST-INAPP-SESSION")
        assert len(plan.steps) >= 2

    @pytest.mark.asyncio
    async def test_34_stop_during_action(self):
        brain = BrainService()
        gen = brain.chat("falso stop", session_id="TEST-INAPP-SESSION")
        responses = [item async for item in gen]
        assert len(responses) > 0

    # ── VOICE ──

    @pytest.mark.asyncio
    async def test_35_voice_calculator(self):
        brain = BrainService()
        gen = brain.chat("add 10 + 10", session_id="TEST-INAPP-SESSION")
        responses = [item async for item in gen]
        assert len(responses) > 0

    @pytest.mark.asyncio
    async def test_36_voice_chrome(self):
        brain = BrainService()
        gen = brain.chat("open chrome", session_id="TEST-INAPP-SESSION")
        responses = [item async for item in gen]
        assert len(responses) > 0

    @pytest.mark.asyncio
    async def test_37_voice_new_tab(self):
        brain = BrainService()
        gen = brain.chat("open a new tab", session_id="TEST-INAPP-SESSION")
        responses = [item async for item in gen]
        assert len(responses) > 0

    @pytest.mark.asyncio
    async def test_38_voice_navigation(self):
        brain = BrainService()
        gen = brain.chat("go to google.com", session_id="TEST-INAPP-SESSION")
        responses = [item async for item in gen]
        assert len(responses) > 0
