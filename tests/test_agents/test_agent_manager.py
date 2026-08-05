import pytest

from agents.manager import AgentManager
from agents.shared_context import SharedTaskContext


@pytest.mark.asyncio
async def test_agent_manager_lifecycle():
    manager = AgentManager(timeout_seconds=5.0)

    agent = manager.create_agent("researcher")
    assert agent.name == "researcher"
    assert "researcher" in manager.list_active_agents()

    assert manager.terminate_agent("researcher") is True
    assert "researcher" not in manager.list_active_agents()


@pytest.mark.asyncio
async def test_agent_manager_safe_execution():
    manager = AgentManager()
    context = SharedTaskContext(task_id="t1", original_prompt="Audit code")

    result = await manager.execute_task_safely("coder", "Audit security", shared_context=context)
    assert result.success is True
    assert context.get_result("coder") is not None

    logs = manager.get_action_logs()
    assert len(logs) >= 2
    assert any(log["action"] == "create" for log in logs)
