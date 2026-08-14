"""
Test Suite for Milestone 2.3: Safe Action & Tool Framework

Tests:
1. Tool Registry & Metadata
2. Tool Input & Output Schemas
3. Read-Only Tools (time, system, cpu_ram, running_apps, active_window, current_project, network_status, filesystem)
4. Permission System & Confirmation Handling
5. Timeout Handling
6. Failure & Exception Isolation
7. Security: Prohibition of Arbitrary Shell Commands
8. Normal Chat & First-Token Streaming Integration
"""

import asyncio
import json
import pytest

from app.tools.base import PermissionLevel, Tool, ToolResult
from app.tools.registry import ToolRegistry
from app.tools.manager import ToolManager
from app.services.brain import BrainService


@ToolRegistry.register
class SlowTestTool(Tool):
    name = "slow_test_tool_99"
    description = "Dummy test tool that simulates a timeout"
    permission_level = PermissionLevel.READ_ONLY
    timeout = 0.2

    @classmethod
    def match_prompt(cls, prompt: str, context=None) -> dict | None:
        if prompt.strip() == "slow_test_tool_99":
            return {}
        return None

    async def execute(self, **kwargs) -> ToolResult:
        await asyncio.sleep(1.0)
        return ToolResult(success=True, data="Should not reach here")


@ToolRegistry.register
class FailingTestTool(Tool):
    name = "failing_test_tool_99"
    description = "Dummy test tool that raises an exception"
    permission_level = PermissionLevel.READ_ONLY
    timeout = 2.0

    @classmethod
    def match_prompt(cls, prompt: str, context=None) -> dict | None:
        if prompt.strip() == "failing_test_tool_99":
            return {}
        return None

    async def execute(self, **kwargs) -> ToolResult:
        raise RuntimeError("Simulated internal tool crash")


@ToolRegistry.register
class DestructiveTestTool(Tool):
    name = "destructive_test_tool_99"
    description = "Dummy test tool requiring confirmation"
    permission_level = PermissionLevel.DESTRUCTIVE
    timeout = 2.0

    @classmethod
    def match_prompt(cls, prompt: str, context=None) -> dict | None:
        if prompt.strip() == "destructive_test_tool_99":
            return {}
        return None

    async def execute(self, **kwargs) -> ToolResult:
        return ToolResult(success=True, data="Action completed")


class FakeToolProvider:
    name = "fake"
    model = "fake-model"

    async def stream_chat(self, messages: list[dict], **kwargs):
        yield type("Chunk", (), {"text": "Tool result explained naturally."})()


class TestSafeActionFramework:

    def test_1_tool_registry_and_metadata(self):
        tools = ToolRegistry.list()
        assert len(tools) >= 8
        names = [t["name"] for t in tools]
        assert "time" in names
        assert "system" in names
        assert "cpu_ram" in names
        assert "running_apps" in names
        assert "active_window" in names
        assert "current_project" in names
        assert "network_status" in names
        assert "file" in names

    def test_2_tool_schemas(self):
        for tool_info in ToolRegistry.list():
            assert "name" in tool_info
            assert "description" in tool_info
            assert "parameters" in tool_info
            assert "output_schema" in tool_info
            assert "permission_level" in tool_info

    @pytest.mark.asyncio
    async def test_3_read_only_tools_execution(self):
        manager = ToolManager()

        # Time tool
        res_time = await manager.execute("time")
        assert res_time.success is True
        assert "time" in res_time.data

        # System tool
        res_sys = await manager.execute("system")
        assert res_sys.success is True
        assert "cpu_model" in res_sys.data

        # Cpu RAM tool
        res_cpu = await manager.execute("cpu_ram")
        assert res_cpu.success is True
        assert "cpu_usage" in res_cpu.data

        # Running apps tool
        res_apps = await manager.execute("running_apps")
        assert res_apps.success is True
        assert isinstance(res_apps.data["running_apps"], list)

        # Active window tool
        res_win = await manager.execute("active_window")
        assert res_win.success is True
        assert "active_app" in res_win.data

        # Current project tool
        res_proj = await manager.execute("current_project")
        assert res_proj.success is True
        assert res_proj.data["current_project"] == "Project-Falso"

        # Network status tool
        res_net = await manager.execute("network_status")
        assert res_net.success is True
        assert res_net.data["network_status"] == "Connected"

    @pytest.mark.asyncio
    async def test_4_permission_system_requires_confirmation(self):
        manager = ToolManager()
        # Unconfirmed destructive action should be blocked
        res = await manager.execute("destructive_test_tool_99")
        assert res.success is False
        assert res.data["confirmation_required"] is True

        # Confirmed action should proceed
        res_confirmed = await manager.execute("destructive_test_tool_99", confirmed=True)
        assert res_confirmed.success is True

    @pytest.mark.asyncio
    async def test_5_tool_timeout(self):
        manager = ToolManager()
        res = await manager.execute("slow_test_tool_99")
        assert res.success is False
        assert "timed out" in res.error.lower()

    @pytest.mark.asyncio
    async def test_6_tool_failure_isolation(self):
        manager = ToolManager()
        res = await manager.execute("failing_test_tool_99")
        assert res.success is False
        assert "Simulated internal tool crash" in res.error

    @pytest.mark.asyncio
    async def test_7_invalid_tool(self):
        manager = ToolManager()
        res = await manager.execute("non_existent_tool_12345")
        assert res.success is False
        assert "Unknown tool" in res.error

    @pytest.mark.asyncio
    async def test_8_security_no_arbitrary_shell_execution(self):
        manager = ToolManager()
        # Arbitrary shell command attempt should fail as invalid tool
        res = await manager.execute("os.system('dir')")
        assert res.success is False
        assert "Unknown tool" in res.error

    @pytest.mark.asyncio
    async def test_9_chat_tool_routing_and_first_token_streaming(self):
        brain = BrainService(provider=FakeToolProvider())
        events = [json.loads(line) async for line in brain.chat("what time is it?")]
        assert len(events) > 0
        assert events[-1]["done"] is True

    @pytest.mark.asyncio
    async def test_10_normal_conversation_unblocked(self):
        brain = BrainService(provider=FakeToolProvider())
        events = [json.loads(line) async for line in brain.chat("Tell me a creative story about space exploration")]
        assert len(events) > 0
        assert events[-1]["done"] is True
