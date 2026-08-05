from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass
class MemoryEntry:
    content: str
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(
        default_factory=lambda: datetime.now(UTC).isoformat()
    )


@dataclass
class MemorySearchResult:
    entry: MemoryEntry
    score: float


class BaseMemoryStore(ABC):
    """Abstract interface for long-term memory persistence."""

    @abstractmethod
    def add(self, content: str, metadata: dict[str, Any] | None = None) -> MemoryEntry:
        """Store a new memory item."""

    @abstractmethod
    def search(self, query: str, limit: int = 5) -> list[MemorySearchResult]:
        """Search stored memories matching query."""

    @abstractmethod
    def delete(self, memory_id: str) -> bool:
        """Delete a memory by ID."""

    @abstractmethod
    def list_all(self, limit: int = 100) -> list[MemoryEntry]:
        """List stored memories up to limit."""

    @abstractmethod
    def clear(self) -> None:
        """Clear all memories."""
