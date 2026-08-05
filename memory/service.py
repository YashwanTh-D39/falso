from __future__ import annotations

import logging

from memory.base import BaseMemoryStore, MemoryEntry, MemorySearchResult
from memory.json_store import JSONMemoryStore

logger = logging.getLogger(__name__)


class MemoryService:
    """Unified memory manager. Auto-detects ChromaDB if available, otherwise
    uses JSONMemoryStore.
    """

    def __init__(self, store: BaseMemoryStore | None = None) -> None:
        if store is not None:
            self.store = store
        else:
            self.store = self._init_store()

    @staticmethod
    def _init_store() -> BaseMemoryStore:
        try:
            from memory.chroma_store import ChromaMemoryStore

            store = ChromaMemoryStore()
            logger.info("MemoryService initialized with ChromaMemoryStore")
            return store
        except ImportError:
            logger.info("ChromaDB not available — MemoryService using JSONMemoryStore")
            return JSONMemoryStore()
        except Exception as e:  # noqa: BLE001
            logger.warning("Failed to initialize ChromaMemoryStore (%s) — falling back to JSONMemoryStore", e)
            return JSONMemoryStore()

    def remember(self, fact: str, category: str = "general") -> MemoryEntry:
        """Store a new fact or preference."""
        return self.store.add(fact, metadata={"category": category})

    def remember_preference(self, key: str, value: str) -> MemoryEntry:
        """Store a user preference (e.g., language, verbosity, style)."""
        content = f"User preference - {key}: {value}"
        return self.store.add(content, metadata={"category": "user_preference", "key": key, "value": value})

    def remember_session_summary(self, conversation_id: str, summary: str) -> MemoryEntry:
        """Store a conversation session summary for long-term recall."""
        content = f"Past conversation summary ({conversation_id}): {summary}"
        return self.store.add(content, metadata={"category": "session_summary", "conversation_id": conversation_id})

    def recall(self, query: str, limit: int = 5) -> list[MemorySearchResult]:
        """Retrieve relevant memories matching query."""
        return self.store.search(query, limit=limit)

    def forget(self, memory_id: str) -> bool:
        """Delete a memory by ID."""
        return self.store.delete(memory_id)

    def list_memories(self, limit: int = 100) -> list[MemoryEntry]:
        """List stored memory entries up to limit."""
        return self.store.list_all(limit=limit)

    def get_context_summary(self, query: str, limit: int = 3) -> str:
        """Format top relevant memories for system prompt context injection."""
        results = self.recall(query, limit=limit)
        if not results:
            return ""
        lines = [f"- {r.entry.content}" for r in results]
        return "Relevant remembered facts:\n" + "\n".join(lines)
