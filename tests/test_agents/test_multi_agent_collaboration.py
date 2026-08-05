import pytest
from fastapi.testclient import TestClient

from agents.orchestrator import AgentOrchestrator
from agents.registry import AgentRegistry
from app.main import app


@pytest.mark.asyncio
async def test_all_specialized_agents_registered():
    agents = AgentRegistry.list_agents()
    names = [a["name"] for a in agents]

    for expected in ("planner", "researcher", "developer", "memory", "automation", "vision"):
        assert expected in names


@pytest.mark.asyncio
async def test_decompose_and_execute():
    orchestrator = AgentOrchestrator()
    res = await orchestrator.decompose_and_execute("Build and deploy long term memory feature")

    assert "task_id" in res
    assert "planner_summary" in res
    assert len(res["agent_results"]) >= 2
    assert "aggregated_response" in res


def test_agent_api_endpoints():
    with TestClient(app) as client:
        # List
        r = client.get("/api/v1/agents/")
        assert r.status_code == 200
        names = [a["name"] for a in r.json()]
        assert "planner" in names

        # Single execute
        r = client.post("/api/v1/agents/execute", json={"agent_name": "developer", "prompt": "Refactor router"})
        assert r.status_code == 200
        assert r.json()["agent"] == "developer"

        # Decompose
        r = client.post("/api/v1/agents/decompose", json={"prompt": "Optimize database queries"})
        assert r.status_code == 200
        assert "aggregated_response" in r.json()
