"""
Test Suite for Milestone 2.1: Persistent Memory Engine

Tests:
1. Create Memory
2. Retrieve Memory
3. Update Memory
4. Forget Memory
5. Relevant Retrieval
6. Irrelevant Memory Exclusion
7. Duplicate Memory Handling
8. Secret/Credential Rejection
9. Memory Persistence Across Restart
10. Normal Chat Integration
"""

import asyncio
import json
import pytest

from memory.json_store import JSONMemoryStore
from memory.service import MemoryService
from memory.secrets import is_sensitive_data
from app.services.brain import BrainService


class FakeChatProvider:
    name = "fake"
    model = "fake-model"

    async def stream_chat(self, messages: list[dict], **kwargs):
        # Inspect system prompt for memory context
        system_content = next((m["content"] for m in messages if m.get("role") == "system"), "")
        user_content = next((m["content"] for m in messages if m.get("role") == "user"), "")

        if "Falso" in system_content or "Falso" in user_content:
            yield type("Chunk", (), {"text": "Falso."})()
        else:
            yield type("Chunk", (), {"text": "Hello there!"})()


class TestPersistentMemoryEngine:

    def test_1_create_memory(self, tmp_path):
        store_file = tmp_path / "memories.json"
        store = JSONMemoryStore(store_file)
        service = MemoryService(store=store)

        entry = service.remember("Falso is my main AI project.", category="project", importance=5, source="user_explicit")
        assert entry.id is not None
        assert entry.content == "Falso is my main AI project."
        assert entry.category == "project"
        assert entry.importance == 5
        assert entry.source == "user_explicit"
        assert entry.created_at != ""
        assert entry.updated_at != ""

    def test_2_retrieve_memory(self, tmp_path):
        store_file = tmp_path / "memories.json"
        store = JSONMemoryStore(store_file)
        service = MemoryService(store=store)

        service.remember("User prefers dark mode UI.", category="preference")
        results = service.recall("dark mode preference", limit=3)
        assert len(results) > 0
        assert "dark mode" in results[0].entry.content
        assert results[0].score > 0.3

    def test_3_update_memory(self, tmp_path):
        store_file = tmp_path / "memories.json"
        store = JSONMemoryStore(store_file)
        service = MemoryService(store=store)

        entry = service.remember("Original fact text", category="general")
        old_updated_at = entry.updated_at

        updated = service.update_memory(entry.id, content="Updated fact text", importance=4)
        assert updated is not None
        assert updated.content == "Updated fact text"
        assert updated.importance == 4

        recalled = service.recall("Updated fact text")
        assert len(recalled) > 0
        assert recalled[0].entry.content == "Updated fact text"

    def test_4_forget_memory(self, tmp_path):
        store_file = tmp_path / "memories.json"
        store = JSONMemoryStore(store_file)
        service = MemoryService(store=store)

        entry = service.remember("Temporary secret fact to delete")
        assert service.forget(entry.id) is True
        assert len(service.recall("Temporary secret fact")) == 0

    def test_5_relevant_retrieval(self, tmp_path):
        store_file = tmp_path / "memories.json"
        store = JSONMemoryStore(store_file)
        service = MemoryService(store=store)

        service.remember("Favorite color is cyan.", category="preference")
        context_summary = service.get_context_summary("What is my favorite color?", min_score=0.3)
        assert "Relevant remembered facts:" in context_summary
        assert "Favorite color is cyan" in context_summary

    def test_6_irrelevant_memory_exclusion(self, tmp_path):
        store_file = tmp_path / "memories.json"
        store = JSONMemoryStore(store_file)
        service = MemoryService(store=store)

        service.remember("Favorite color is cyan.", category="preference")
        # Querying about completely unrelated topic (quantum mechanics physics)
        context_summary = service.get_context_summary("Tell me about quantum electrodynamics", min_score=0.35)
        assert context_summary == ""

    def test_7_duplicate_memory_handling(self, tmp_path):
        store_file = tmp_path / "memories.json"
        store = JSONMemoryStore(store_file)
        service = MemoryService(store=store)

        entry1 = service.remember("Falso is my main AI project.")
        entry2 = service.remember("falso is my main ai project.")
        
        # Duplicate detection should update existing entry rather than creating a duplicate
        assert entry1.id == entry2.id
        all_memories = service.list_memories()
        assert len(all_memories) == 1

    def test_8_secret_credential_rejection(self, tmp_path):
        store_file = tmp_path / "memories.json"
        store = JSONMemoryStore(store_file)
        service = MemoryService(store=store)

        # Test API key rejection
        with pytest.raises(ValueError, match="Sensitive credentials"):
            service.remember("My API key is sk-proj-1234567890abcdef1234567890")

        # Test password rejection
        with pytest.raises(ValueError, match="Sensitive credentials"):
            service.remember("My password is SuperSecretPassword123!")

        # Verify nothing was stored
        assert len(service.list_memories()) == 0

    def test_9_memory_persistence_across_restart(self, tmp_path):
        store_file = tmp_path / "memories.json"

        # Session 1: Store memory
        store1 = JSONMemoryStore(store_file)
        service1 = MemoryService(store=store1)
        service1.remember("Persistent fact saved to disk.")

        # Session 2: Reload from disk
        store2 = JSONMemoryStore(store_file)
        service2 = MemoryService(store=store2)
        memories = service2.list_memories()
        assert len(memories) == 1
        assert memories[0].content == "Persistent fact saved to disk."

    @pytest.mark.asyncio
    async def test_10_normal_chat_integration(self, tmp_path):
        store_file = tmp_path / "memories.json"
        store = JSONMemoryStore(store_file)
        service = MemoryService(store=store)
        brain = BrainService(provider=FakeChatProvider(), memory_service=service)

        # Explicit command
        events1 = [json.loads(line) async for line in brain.chat("remember that Falso is my main AI project")]
        assert "remember" in events1[0]["response"].lower()

        # Query using remembered context
        events2 = [json.loads(line) async for line in brain.chat("What is my main AI project?")]
        full_resp = "".join(e.get("response", "") for e in events2)
        assert "Falso" in full_resp
