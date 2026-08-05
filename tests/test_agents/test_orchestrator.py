import pytest

from agents.orchestrator import AgentOrchestrator
from agents.registry import AgentRegistry


@pytest.mark.asyncio
async def test_agent_registry_and_list():
    agents = AgentRegistry.list_agents()
    names = [a["name"] for a in agents]
    assert "researcher" in names
    assert "coder" in names
    assert "analyst" in names


@pytest.mark.asyncio
async def test_invoke_single_agent():
    orchestrator = AgentOrchestrator()
    result = await orchestrator.invoke_agent("researcher", "Investigate API performance")
    assert result.success is True
    assert result.agent_name == "researcher"
    assert "Investigate API performance" in result.response


@pytest.mark.asyncio
async def test_invoke_unknown_agent():
    orchestrator = AgentOrchestrator()
    result = await orchestrator.invoke_agent("nonexistent", "Do something")
    assert result.success is False
    assert "Unknown agent" in result.response


@pytest.mark.asyncio
async def test_invoke_parallel_agents():
    orchestrator = AgentOrchestrator()
    results = await orchestrator.invoke_parallel([
        ("researcher", "Search docs"),
        ("coder", "Draft function"),
    ])
    assert len(results) == 2
    assert results[0].agent_name == "researcher"
    assert results[1].agent_name == "coder"
    assert all(r.success for r in results)
