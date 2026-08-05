from memory.json_store import JSONMemoryStore
from memory.service import MemoryService


class TestJSONMemoryStore:
    def test_add_and_list(self, tmp_path):
        store_file = tmp_path / "memories.json"
        store = JSONMemoryStore(store_file)
        
        m1 = store.add("User prefers dark mode", metadata={"category": "pref"})
        assert m1.content == "User prefers dark mode"
        assert m1.metadata == {"category": "pref"}

        all_m = store.list_all()
        assert len(all_m) == 1
        assert all_m[0].id == m1.id

    def test_search(self, tmp_path):
        store_file = tmp_path / "memories.json"
        store = JSONMemoryStore(store_file)

        store.add("User lives in New York City")
        store.add("User works as a software engineer in Python")
        store.add("Favorite color is blue")

        results = store.search("software engineer Python", limit=2)
        assert len(results) >= 1
        assert "software engineer" in results[0].entry.content

    def test_delete_and_clear(self, tmp_path):
        store_file = tmp_path / "memories.json"
        store = JSONMemoryStore(store_file)

        m1 = store.add("Fact one")
        store.add("Fact two")

        assert store.delete(m1.id) is True
        assert len(store.list_all()) == 1

        store.clear()
        assert len(store.list_all()) == 0


class TestMemoryService:
    def test_remember_and_recall(self, tmp_path):
        store_file = tmp_path / "memories.json"
        store = JSONMemoryStore(store_file)
        service = MemoryService(store=store)

        service.remember("The user's favorite language is Python", category="user_info")
        results = service.recall("Python language")

        assert len(results) > 0
        assert "Python" in results[0].entry.content

    def test_get_context_summary(self, tmp_path):
        store_file = tmp_path / "memories.json"
        store = JSONMemoryStore(store_file)
        service = MemoryService(store=store)

        service.remember("Project is named Falso")
        summary = service.get_context_summary("Falso")
        assert "Falso" in summary
        assert "Relevant remembered facts:" in summary

    def test_forget(self, tmp_path):
        store_file = tmp_path / "memories.json"
        store = JSONMemoryStore(store_file)
        service = MemoryService(store=store)

        entry = service.remember("Temporary memory")
        assert service.forget(entry.id) is True
        assert len(service.recall("Temporary")) == 0
