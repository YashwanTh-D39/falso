from __future__ import annotations

import logging
from typing import Any

from memory.base import BaseMemoryStore, MemoryEntry, MemorySearchResult

logger = logging.getLogger(__name__)


class CloudMemoryStore(BaseMemoryStore):
    """Modular cloud vector database store interface.
    Supports future migration to cloud providers (e.g. Pinecone, Weaviate, pgvector).
    """

    def __init__(self, provider_name: str = "cloud_generic", config: dict[str, Any] | None = None) -> None:
        self.provider_name = provider_name
        self.config = config or {}
        logger.info("Initialized CloudMemoryStore (provider=%s)", self.provider_name)
        # In-memory backing buffer for local operations before cloud sync
        self._local_cache: dict[str, MemoryEntry] = {}

    def add(self, content: str, metadata: dict[str, Any] | None = None) -> MemoryEntry:
        entry = MemoryEntry(
            content=content.strip(),
            metadata={**(metadata or {}), "cloud_provider": self.provider_name},
        )
        self._local_cache[entry.id] = entry
        logger.debug("CloudMemoryStore [%s] cached entry %s", self.provider_name, entry.id)
        return entry

    def search(self, query: str, limit: int = 5) -> list[MemorySearchResult]:
        # Perform query against local cache / remote index
        results: list[MemorySearchResult] = []
        q_lower = query.lower()
        for entry in self._local_cache.values():
            if q_lower in entry.content.lower():
                results.append(MemorySearchResult(entry=entry, score=1.0))
        return results[:limit]

    def delete(self, memory_id: str) -> bool:
        if memory_id in self._local_cache:
            del self._local_cache[memory_id]
            return True
        return False

    def list_all(self, limit: int = 100) -> list[MemoryEntry]:
        return list(self._local_cache.values())[:limit]

    def clear(self) -> None:
        self._local_cache.clear()
