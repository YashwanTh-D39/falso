"""
Unit tests for FALSO 4.2 Controlled App Interaction + Graceful App Close.
"""

from unittest.mock import patch, MagicMock
import pytest

from app.services.automation.autopilot import autopilot_agent
from app.services.automation.goal_planner import goal_planner
from app.services.automation.permissions import permission_manager
from app.services.automation.windows.executor import windows_executor
from app.services.automation.windows.window_manager import window_manager


class TestControlledInteractionAndClose:

    @pytest.mark.asyncio
    async def test_01_open_calculator(self):
        with patch.object(window_manager, "is_window_open", return_value=True), \
             patch.object(window_manager, "focus_window", return_value=True), \
             patch.object(window_manager, "verify_foreground", return_value=True):
            resp = await autopilot_agent.run_goal("Open Calculator")
            assert resp == "Calculator is open."

    def test_02_focus_calculator(self):
        with patch.object(window_manager, "is_window_open", return_value=True), \
             patch.object(window_manager, "focus_window", return_value=True):
            plan = goal_planner.create_plan("Focus Calculator")
            assert any(s.action == "focus_window" for s in plan.steps)

    def test_03_interact_with_calculator(self):
        with patch.object(window_manager, "is_window_open", return_value=True), \
             patch.object(window_manager, "focus_window", return_value=True):
            plan = goal_planner.create_plan("calculate 10 + 10")
            assert any(s.action == "interact_with_app" for s in plan.steps)

    @pytest.mark.asyncio
    async def test_04_calculate_10_plus_10(self):
        with patch.object(window_manager, "is_window_open", return_value=True), \
             patch.object(window_manager, "focus_window", return_value=True), \
             patch.object(window_manager, "verify_foreground", return_value=True):
            resp = await autopilot_agent.run_goal("add 10 + 10")
            assert resp == "20."

    @pytest.mark.asyncio
    async def test_05_verify_result_20(self):
        with patch.object(window_manager, "is_window_open", return_value=True), \
             patch.object(window_manager, "focus_window", return_value=True), \
             patch.object(window_manager, "verify_foreground", return_value=True):
            resp = await autopilot_agent.run_goal("what is 25 * 4 in calculator")
            assert resp == "100."

    @pytest.mark.asyncio
    async def test_06_close_calculator(self):
        with patch.object(window_manager, "close_window", return_value={"success": True, "unsaved_changes": False}), \
             patch.object(window_manager, "is_window_open", return_value=False):
            resp = await autopilot_agent.run_goal("close Calculator")
            assert resp == "Calculator is closed."

    @pytest.mark.asyncio
    async def test_07_open_notepad(self):
        with patch.object(window_manager, "is_window_open", return_value=True), \
             patch.object(window_manager, "focus_window", return_value=True), \
             patch.object(window_manager, "verify_foreground", return_value=True):
            resp = await autopilot_agent.run_goal("Open Notepad")
            assert resp == "Notepad is open."

    def test_08_type_text_into_notepad(self):
        with patch.object(window_manager, "is_window_open", return_value=True), \
             patch.object(window_manager, "focus_window", return_value=True):
            plan = goal_planner.create_plan("open notepad and type hello")
            assert any(s.action == "type_text" for s in plan.steps)

    @pytest.mark.asyncio
    async def test_09_close_notepad(self):
        with patch.object(window_manager, "close_window", return_value={"success": True, "unsaved_changes": False}), \
             patch.object(window_manager, "is_window_open", return_value=False):
            resp = await autopilot_agent.run_goal("close Notepad")
            assert resp == "Notepad is closed."

    @pytest.mark.asyncio
    async def test_10_detect_unsaved_notepad_content(self):
        with patch.object(window_manager, "close_window", return_value={"success": False, "unsaved_changes": True, "reason": "*Untitled - Notepad has unsaved changes."}):
            resp = await autopilot_agent.run_goal("close Notepad")
            assert "unsaved changes" in resp.lower()

    @pytest.mark.asyncio
    async def test_11_refuse_force_close_of_unsaved_content(self):
        with patch.object(window_manager, "close_window", return_value={"success": False, "unsaved_changes": True}):
            resp = await autopilot_agent.run_goal("close Notepad")
            assert "won't close it without confirmation" in resp

    @pytest.mark.asyncio
    async def test_12_open_chrome(self):
        with patch.object(window_manager, "is_window_open", return_value=True), \
             patch.object(window_manager, "focus_window", return_value=True), \
             patch.object(window_manager, "verify_foreground", return_value=True):
            resp = await autopilot_agent.run_goal("open chrome")
            assert resp == "Chrome is open."

    @pytest.mark.asyncio
    async def test_13_close_chrome(self):
        with patch.object(window_manager, "close_window", return_value={"success": True, "unsaved_changes": False}), \
             patch.object(window_manager, "is_window_open", return_value=False):
            resp = await autopilot_agent.run_goal("close chrome")
            assert resp == "Chrome is closed."

    def test_14_permission_denial_non_allowlisted_app(self):
        res = permission_manager.check_capability("windows.launch_app", target="malware_app.exe")
        assert not res.allowed
        assert "not in approved" in res.reason

    def test_15_permission_denial_arbitrary_process_termination(self):
        res = permission_manager.check_capability("windows.kill_process", target="system_proc.exe")
        risk = permission_manager.get_risk_level("kill_process", target="system_proc.exe")
        assert risk.name == "HIGH"

    def test_16_permission_denial_arbitrary_shell_execution(self):
        res = permission_manager.check_command_execution("powershell_raw", args=["Remove-Item -Recurse C:\\"])
        assert not res.allowed

    @pytest.mark.asyncio
    async def test_17_voice_calculator(self):
        with patch.object(window_manager, "is_window_open", return_value=True), \
             patch.object(window_manager, "focus_window", return_value=True), \
             patch.object(window_manager, "verify_foreground", return_value=True):
            resp = await autopilot_agent.run_goal("calculate 15 minus 3")
            assert resp == "12."

    @pytest.mark.asyncio
    async def test_18_voice_close_calculator(self):
        with patch.object(window_manager, "close_window", return_value={"success": True, "unsaved_changes": False}), \
             patch.object(window_manager, "is_window_open", return_value=False):
            resp = await autopilot_agent.run_goal("close calculator")
            assert resp == "Calculator is closed."

    @pytest.mark.asyncio
    async def test_19_falso_stop_during_interaction(self):
        autopilot_agent.cancel_active_task()
        resp = await autopilot_agent.run_goal("open calculator")
        assert resp in ("Cancelled.", "Calculator is open.", "I couldn't open Calculator.")

    @pytest.mark.asyncio
    async def test_20_recovery_after_failed_ui_interaction(self):
        with patch.object(windows_executor, "execute_action", side_effect=[{"success": False}, {"success": True}]), \
             patch.object(window_manager, "is_window_open", return_value=True):
            resp = await autopilot_agent.run_goal("open calculator")
            assert resp in ("Calculator is open.", "I couldn't open Calculator.")
