from fastapi.testclient import TestClient

from app.main import app
from memory.cloud_store import CloudMemoryStore
from memory.service import MemoryService


def test_memory_service_session_and_preferences(tmp_path):
    from memory.json_store import JSONMemoryStore
    store = JSONMemoryStore(tmp_path / "mem.json")
    service = MemoryService(store=store)

    p = service.remember_preference("theme", "dark")
    assert p.metadata["category"] == "user_preference"
    assert "theme" in p.content

    s = service.remember_session_summary("conv-123", "Discussed performance and memory architecture")
    assert s.metadata["category"] == "session_summary"
    assert s.metadata["conversation_id"] == "conv-123"

    recalled = service.recall("theme dark", limit=5)
    assert len(recalled) > 0


def test_cloud_memory_store_interface():
    cloud_store = CloudMemoryStore(provider_name="pinecone_stub")
    e1 = cloud_store.add("Fact backed by cloud")
    assert e1.metadata["cloud_provider"] == "pinecone_stub"

    res = cloud_store.search("cloud")
    assert len(res) == 1
    assert cloud_store.delete(e1.id) is True


def test_memory_api_endpoints():
    with TestClient(app) as client:
        # Create
        r = client.post("/api/v1/memory/", json={"content": "User prefers dark mode UI", "category": "preference"})
        assert r.status_code == 200
        data = r.json()
        assert "id" in data
        mem_id = data["id"]

        # List
        r = client.get("/api/v1/memory/")
        assert r.status_code == 200
        assert len(r.json()) > 0

        # Search
        r = client.post("/api/v1/memory/search", json={"query": "dark mode", "limit": 2})
        assert r.status_code == 200
        assert len(r.json()) > 0

        # Delete
        r = client.delete(f"/api/v1/memory/{mem_id}")
        assert r.status_code == 200
        assert r.json() == {"ok": True}
