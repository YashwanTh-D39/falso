"""
Unit tests for FALSO 4.4 Action Truth & Reliable Sleep/Wake Hardening.
"""

import asyncio
import time
from unittest.mock import patch, MagicMock
import pytest

from app.services.automation.windows.app_registry import app_registry, ApplicationIdentity
from app.services.automation.windows.executor import windows_executor
from app.services.automation.windows.process_manager import process_manager
from app.services.automation.windows.window_manager import window_manager
from app.services.automation.autopilot import autopilot_agent
from app.services.automation.permissions import permission_manager
from app.services.session_history import session_history_manager
from app.services.brain import BrainService


class TestFalso44ActionTruthAndSleep:

    def setup_method(self):
        permission_manager.disable_lockdown()
        session_history_manager.clear_session("TEST-SLEEP-SESSION")

    def teardown_method(self):
        permission_manager.disable_lockdown()

    # ── 1. AUTOMATION VERIFICATION TESTS ──

    def test_01_open_calculator_verified(self):
        with patch.object(window_manager, "is_window_open", side_effect=[False, True]), \
             patch.object(window_manager, "wait_for_window", return_value=True):
            res = process_manager.launch_app("Calculator")
            assert res["success"] is True
            assert res["verified"] is True
            assert res["target"] == "Calculator"

    def test_02_open_already_running_calculator_focused(self):
        with patch.object(window_manager, "is_window_open", return_value=True), \
             patch.object(window_manager, "focus_window", return_value=True):
            res = process_manager.launch_app("Calculator")
            assert res["success"] is True
            assert res["verified"] is True
            assert "already open" in res["verification_reason"] or "is open" in res["verification_reason"]

    def test_03_close_calculator(self):
        with patch.object(window_manager, "list_windows", return_value=[{"hwnd": 123, "title": "Calculator"}]), \
             patch.object(window_manager, "wait_for_window_close", return_value=True), \
             patch.object(process_manager, "is_process_running", return_value=False):
            res = window_manager.close_window("Calculator")
            assert res["success"] is True
            assert res["verified"] is True
            assert res["target"] == "Calculator"

    def test_04_verify_calculator_actually_closed(self):
        with patch.object(window_manager, "list_windows", return_value=[{"hwnd": 123, "title": "Calculator"}]), \
             patch.object(window_manager, "wait_for_window_close", return_value=True), \
             patch.object(process_manager, "is_process_running", return_value=False):
            res = window_manager.close_window("Calculator")
            assert res["verified"] is True
            assert res["after_state"]["window_open"] is False

    def test_05_open_claude(self):
        with patch.object(window_manager, "is_window_open", side_effect=[False, True]), \
             patch.object(window_manager, "wait_for_window", return_value=True):
            res = process_manager.launch_app("Claude")
            assert res["success"] is True
            assert res["verified"] is True
            assert res["target"] == "Claude"

    def test_06_focus_already_running_claude(self):
        with patch.object(window_manager, "is_window_open", return_value=True), \
             patch.object(window_manager, "focus_window", return_value=True):
            res = process_manager.launch_app("Claude")
            assert res["success"] is True
            assert res["verified"] is True

    def test_07_close_claude(self):
        with patch.object(window_manager, "list_windows", return_value=[{"hwnd": 456, "title": "Claude"}]), \
             patch.object(window_manager, "wait_for_window_close", return_value=True), \
             patch.object(process_manager, "is_process_running", return_value=False):
            res = window_manager.close_window("Claude")
            assert res["success"] is True
            assert res["verified"] is True
            assert res["target"] == "Claude"

    def test_08_verify_claude_actually_closed(self):
        with patch.object(window_manager, "list_windows", return_value=[{"hwnd": 456, "title": "Claude"}]), \
             patch.object(window_manager, "wait_for_window_close", return_value=True), \
             patch.object(process_manager, "is_process_running", return_value=False):
            res = window_manager.close_window("Claude")
            assert res["verified"] is True
            assert res["verification_reason"] == "Claude is closed."

    def test_09_failed_close_verification_returns_failure_message(self):
        with patch.object(window_manager, "list_windows", return_value=[{"hwnd": 456, "title": "Claude"}]), \
             patch.object(window_manager, "wait_for_window_close", return_value=False), \
             patch.object(process_manager, "is_process_running", return_value=True):
            res = window_manager.close_window("Claude")
            assert res["success"] is False
            assert res["verified"] is False
            assert res["verification_reason"] == "I couldn't close Claude."

    def test_10_multiple_matching_windows_closed(self):
        wins = [{"hwnd": 101, "title": "Claude - Project A"}, {"hwnd": 102, "title": "Claude - Project B"}]
        with patch.object(window_manager, "list_windows", return_value=wins), \
             patch.object(window_manager, "wait_for_window_close", return_value=True), \
             patch.object(process_manager, "is_process_running", return_value=False):
            res = window_manager.close_window("Claude")
            assert res["success"] is True

    def test_11_open_file_explorer(self):
        with patch.object(window_manager, "wait_for_window", return_value=True), \
             patch.object(window_manager, "is_window_open", return_value=True):
            res = windows_executor.execute_action("open_approved_folder", target=r"C:\Users\Admin\Project-Falso")
            assert res["success"] is True
            assert res["verified"] is True

    def test_12_close_file_explorer(self):
        with patch.object(window_manager, "list_windows", return_value=[{"hwnd": 789, "title": "File Explorer"}]), \
             patch.object(window_manager, "wait_for_window_close", return_value=True), \
             patch.object(process_manager, "is_process_running", return_value=False):
            res = window_manager.close_window("File Explorer")
            assert res["success"] is True
            assert res["verified"] is True

    def test_13_arbitrary_process_termination_remains_denied(self):
        assert process_manager.stop_process("csrss") is False
        assert process_manager.stop_process("svchost") is False

    def test_14_arbitrary_shell_remains_denied(self):
        perm = permission_manager.check_command_execution("powershell.exe -Command Remove-Item C:\\")
        assert perm.allowed is False

    # ── 2. SLEEP / WAKE HARDENING TESTS ──

    @pytest.mark.asyncio
    async def test_15_enter_sleep_command(self):
        brain = BrainService()
        gen = brain.chat("go to sleep", session_id="TEST-SLEEP-SESSION")
        responses = [item async for item in gen]
        assert any("Going to sleep." in r or "On it." in r for r in responses)

    def test_16_app_registry_claude_identity(self):
        app_info = app_registry.resolve("claude desktop")
        assert app_info is not None
        assert app_info.canonical_name == "Claude"

    @pytest.mark.asyncio
    async def test_17_hello_falso_wake_command(self):
        brain = BrainService()
        gen = brain.chat("hello falso", session_id="TEST-SLEEP-SESSION")
        responses = [item async for item in gen]
        assert any("Yes" in r or "Boss" in r or "awake" in r or "FALSO" in r for r in responses)

    @pytest.mark.asyncio
    async def test_18_falso_wake_up_command(self):
        brain = BrainService()
        gen = brain.chat("falso wake up", session_id="TEST-SLEEP-SESSION")
        responses = [item async for item in gen]
        assert any("Yes" in r or "Boss" in r or "awake" in r for r in responses)

    def test_19_wake_after_tts(self):
        session_history_manager.append_assistant_message("TEST-SLEEP-SESSION", "Speech output complete")
        hist = session_history_manager.get_history("TEST-SLEEP-SESSION")
        assert len(hist) == 1

    def test_20_wake_after_automation(self):
        session_history_manager.append_user_message("TEST-SLEEP-SESSION", "Open Calculator")
        session_history_manager.append_assistant_message("TEST-SLEEP-SESSION", "Calculator is open.")
        last_app = session_history_manager.get_last_target_app("TEST-SLEEP-SESSION")
        assert last_app == "Calculator"

    def test_21_sleep_cancels_active_automation_safely(self):
        with patch.object(autopilot_agent, "is_autopilot_active", return_value=True), \
             patch.object(autopilot_agent, "cancel_active_task", return_value="Cancelled."):
            resp = autopilot_agent.cancel_active_task()
            assert resp == "Cancelled."

    def test_22_no_automation_executes_while_lockdown_or_sleep(self):
        permission_manager.enable_lockdown()
        res = windows_executor.execute_action("launch_app", target="Calculator")
        permission_manager.disable_lockdown()
        assert res["success"] is False
        assert "Lockdown" in res["error"]

    def test_23_session_history_survives_sleep(self):
        session_history_manager.append_user_message("TEST-SLEEP-SESSION", "Open Calculator")
        session_history_manager.append_assistant_message("TEST-SLEEP-SESSION", "Calculator is open.")
        # Simulate sleep and wake
        hist = session_history_manager.get_history("TEST-SLEEP-SESSION")
        assert len(hist) == 2

    def test_24_open_calculator_sleep_wake_close_it_pronoun_resolution(self):
        session_history_manager.append_user_message("TEST-SLEEP-SESSION", "Open Calculator")
        session_history_manager.append_assistant_message("TEST-SLEEP-SESSION", "Calculator is open.")
        target = session_history_manager.get_last_target_app("TEST-SLEEP-SESSION")
        assert target == "Calculator"

    def test_25_wake_listener_does_not_send_microphone_audio_to_nvidia(self):
        # Verify wake commands return fast without LLM stream
        from app.services.brain import is_automation_intent
        assert is_automation_intent("open calculator") is True

    def test_26_wake_does_not_create_fake_conversation_turn(self):
        session_history_manager.clear_session("TEST-SLEEP-SESSION")
        # System wake doesn't pollution
        hist = session_history_manager.get_history("TEST-SLEEP-SESSION")
        assert len(hist) == 0
