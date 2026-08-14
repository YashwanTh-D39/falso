"""
Test Suite for Autopilot Agent Core & Stub Behavior Verification.

Tests:
1. Autopilot Mode Activation & Stub Workflow Response
2. Stub workflows (prepare_dev_environment, organize_downloads, run_and_fix_tests) return "I can't automate that yet." and status=FAILED
3. Instant Cancellation & User Interruption ("FALSO stop")
4. Task Observation & PC State Perception
"""

import json
import pytest

from app.services.automation.autopilot import (
    autopilot_agent,
    AutopilotAgent,
    OperatingMode,
    TaskStatus,
)
from app.services.brain import BrainService


class FakeAutopilotProvider:
    name = "fake"
    model = "fake-model"

    async def stream_chat(self, messages: list[dict], **kwargs):
        yield type("Chunk", (), {"text": "Done."})()


class TestAutopilotAgent:

    @pytest.mark.asyncio
    async def test_1_autopilot_mode_trigger_and_acknowledgment(self):
        brain = BrainService(provider=FakeAutopilotProvider())
        events = [json.loads(line) async for line in brain.chat("FALSO, prepare my FALSO development environment")]
        assert len(events) >= 2
        first_resp = events[0].get("response", "")
        assert first_resp == "On it."
        full_text = "".join(e.get("response", "") for e in events)
        assert "I can't automate that yet." in full_text

    @pytest.mark.asyncio
    async def test_2_workflow_prepare_dev_environment_autonomous_loop(self):
        agent = AutopilotAgent()
        result = await agent.run_goal("Prepare my FALSO development environment", task_id="TEST-DEV-01")
        assert result == "I can't automate that yet."
        assert len(agent.completed_tasks) > 0
        task = agent.completed_tasks[-1]
        assert task.status == TaskStatus.FAILED
        assert task.error_message == "NOT_IMPLEMENTED"

    @pytest.mark.asyncio
    async def test_3_workflow_organize_downloads(self):
        agent = AutopilotAgent()
        result = await agent.run_goal("Organize my Downloads folder", task_id="TEST-DL-01")
        assert result == "I can't automate that yet."
        task = agent.completed_tasks[-1]
        assert task.status == TaskStatus.FAILED
        assert task.error_message == "NOT_IMPLEMENTED"

    @pytest.mark.asyncio
    async def test_4_workflow_run_and_fix_tests(self):
        agent = AutopilotAgent()
        result = await agent.run_goal("Run the tests and fix failures", task_id="TEST-PYTEST-01")
        assert result == "I can't automate that yet."
        task = agent.completed_tasks[-1]
        assert task.status == TaskStatus.FAILED
        assert task.error_message == "NOT_IMPLEMENTED"

    @pytest.mark.asyncio
    async def test_5_instant_user_interruption_and_cancellation(self):
        brain = BrainService(provider=FakeAutopilotProvider())
        # Start goal and trigger cancellation
        autopilot_agent.mode = OperatingMode.AUTOPILOT
        autopilot_agent.active_task = type("Task", (), {"task_id": "ACTIVE-01", "status": TaskStatus.IN_PROGRESS, "end_time": None})()

        events = [json.loads(line) async for line in brain.chat("FALSO stop")]
        assert len(events) > 0
        full_text = "".join(e.get("response", "") for e in events)
        assert "Cancelled." in full_text
        assert autopilot_agent.mode == OperatingMode.NORMAL

    def test_6_task_memory_state(self):
        agent = AutopilotAgent()
        obs = agent._observe_pc()
        assert "active_app" in obs
        assert "running_apps" in obs
        assert "project_name" in obs
        assert obs["project_name"] == "Project-Falso"
