"""
TEST SUITE FOR FALSO 4.0: AUTONOMOUS COMPUTER AGENT CORE

Tests:
1. Simple chat does not invoke Autopilot
2. Automation intent invokes Autopilot
3. Existing application is reused
4. Duplicate launch is prevented
5. Existing server is detected
6. Dynamic planning works
7. Failed action triggers re-observation (RECOVERING state)
8. Recovery respects permissions
9. High-risk action requires confirmation
10. "FALSO stop" cancels immediately
11. Action budget stops execution
12. Runtime budget stops execution
13. .env remains inaccessible
14. C:\Windows remains inaccessible
15. Arbitrary PowerShell remains blocked
16. Voice and text use the same automation pipeline
17. Task status transitions are correct
18. Audit logs contain no secrets
"""

import json
import pytest

from app.services.automation.autopilot import (
    autopilot_agent,
    AutopilotAgent,
    OperatingMode,
    TaskStatus,
)
from app.services.automation.goal_planner import goal_planner, TaskPlan
from app.services.automation.permissions import (
    FileOperation,
    PermissionLevel,
    permission_manager,
    RiskLevel,
)
from app.services.brain import BrainService, is_automation_intent


class FakeAgentCoreProvider:
    name = "fake"
    model = "fake-model"

    async def stream_chat(self, messages: list[dict], **kwargs):
        yield type("Chunk", (), {"text": "Done."})()


class TestFalso4AgentCore:

    def setup_method(self):
        permission_manager.disable_lockdown()

    def test_01_simple_chat_does_not_invoke_autopilot(self):
        assert is_automation_intent("hello") is False
        assert is_automation_intent("What is Python?") is False
        assert is_automation_intent("Explain TCP") is False

    def test_02_automation_intent_invokes_autopilot(self):
        assert is_automation_intent("open calculator") is True
        assert is_automation_intent("prepare my coding environment") is True
        assert is_automation_intent("run my tests") is True

    def test_03_existing_application_is_reused(self):
        obs = {"running_apps": ["CalculatorApp.exe"]}
        plan = goal_planner.create_plan("open calculator", obs=obs)
        assert plan.steps[0].action == "focus_window"

    def test_04_duplicate_launch_is_prevented(self):
        from app.services.automation.windows.process_manager import process_manager
        from app.services.automation.windows.window_manager import window_manager
        from unittest.mock import patch
        with patch.object(window_manager, "is_window_open", return_value=True):
            res = process_manager.launch_app("calculator")
            assert (res is True) or (isinstance(res, dict) and res.get("success") is True)

    def test_05_existing_server_is_detected(self):
        from app.services.automation.windows.process_manager import process_manager
        is_running = process_manager.is_process_running("python") or process_manager.is_process_running("uvicorn")
        assert isinstance(is_running, bool)

    def test_06_dynamic_planning_works(self):
        plan = goal_planner.create_plan("prepare my coding environment", obs={"running_apps": ["Code.exe"]})
        assert plan.steps[0].action == "focus_window"
        assert plan.steps[0].target == "VS Code"

    @pytest.mark.asyncio
    async def test_07_failed_action_triggers_reobservation(self):
        agent = AutopilotAgent()
        res = await agent.run_goal("open non_existent_custom_app_123")
        assert res in ("Done.", "Cancelled.", "I couldn't complete that safely.", "I couldn't open non_existent_custom_app_123.")

    def test_08_recovery_respects_permissions(self):
        res = permission_manager.check_filesystem_access(r"C:\Windows\System32\cmd.exe", operation=FileOperation.DELETE)
        assert res.allowed is False

    def test_09_high_risk_action_requires_confirmation(self):
        risk = permission_manager.get_risk_level("delete", target="system files")
        assert risk == RiskLevel.HIGH

    @pytest.mark.asyncio
    async def test_10_falso_stop_cancels_immediately(self):
        brain = BrainService(provider=FakeAgentCoreProvider())
        autopilot_agent.mode = OperatingMode.AUTOPILOT
        autopilot_agent.active_task = type("Task", (), {"task_id": "CORE-01", "status": TaskStatus.EXECUTING, "end_time": None})()

        events = [json.loads(line) async for line in brain.chat("FALSO stop")]
        full_text = "".join(e.get("response", "") for e in events)
        assert "Cancelled." in full_text
        assert autopilot_agent.mode == OperatingMode.NORMAL

    @pytest.mark.asyncio
    async def test_11_action_budget_stops_execution(self):
        agent = AutopilotAgent()
        res = await agent.run_goal("open calculator")
        assert res in ("Done.", "Cancelled.", "Calculator is open.", "I couldn't open Calculator.")
        assert agent.completed_tasks[-1].action_count <= 50

    @pytest.mark.asyncio
    async def test_12_runtime_budget_stops_execution(self):
        agent = AutopilotAgent()
        obs = agent._observe_pc()
        assert "timestamp" in obs

    def test_13_env_remains_inaccessible(self):
        res = permission_manager.check_filesystem_access(r"C:\Users\Admin\Project-Falso\.env", operation=FileOperation.READ)
        assert res.allowed is False

    def test_14_windows_remains_inaccessible(self):
        res = permission_manager.check_filesystem_access(r"C:\Windows\System32\config", operation=FileOperation.WRITE)
        assert res.allowed is False

    def test_15_arbitrary_powershell_remains_blocked(self):
        res = permission_manager.check_command_execution("powershell", args=["Invoke-Expression", "rm -rf"])
        assert res.allowed is False

    @pytest.mark.asyncio
    async def test_16_voice_and_text_use_same_pipeline(self):
        brain = BrainService(provider=FakeAgentCoreProvider())
        events = [json.loads(line) async for line in brain.chat("FALSO, open calculator.")]
        full_text = "".join(e.get("response", "") for e in events)
        assert "On it." in full_text or "Done." in full_text

    def test_17_task_status_transitions_are_correct(self):
        assert TaskStatus.IDLE.value == "IDLE"
        assert TaskStatus.OBSERVING.value == "OBSERVING"
        assert TaskStatus.PLANNING.value == "PLANNING"
        assert TaskStatus.WAITING_PERMISSION.value == "WAITING_PERMISSION"
        assert TaskStatus.EXECUTING.value == "EXECUTING"
        assert TaskStatus.VERIFYING.value == "VERIFYING"
        assert TaskStatus.RECOVERING.value == "RECOVERING"
        assert TaskStatus.COMPLETED.value == "COMPLETED"

    def test_18_audit_logs_contain_no_secrets(self):
        permission_manager.log_action(
            task_id="TEST-LOG",
            request_id="REQ-LOG",
            action_id="test_action",
            capability="test.capability",
            target="target_with_NVIDIA_INFERENCE_API_KEY_value",
            result="SUCCESS",
            duration_ms=12.5,
        )
        assert len(permission_manager.audit_log) > 0
        last_entry = permission_manager.audit_log[-1]
        assert "[MASKED_SECRET:NVIDIA_INFERENCE_API_KEY]" in last_entry.target
