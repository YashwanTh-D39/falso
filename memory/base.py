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
    category: str = "general"
    importance: int = 1
    source: str = "USER_EXPLICIT"
    confidence: str = "HIGH"
    classification: str = "PERSISTENT"
    scope: str = "GLOBAL"
    key: str = ""
    value: str = ""
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(
        default_factory=lambda: datetime.now(UTC).isoformat()
    )
    updated_at: str = field(
        default_factory=lambda: datetime.now(UTC).isoformat()
    )
    last_used_at: str = field(
        default_factory=lambda: datetime.now(UTC).isoformat()
    )
    expires_at: str | None = None

    def __post_init__(self) -> None:
        # Sync metadata dictionary with class fields for compatibility
        if "category" in self.metadata and self.metadata["category"]:
            self.category = str(self.metadata["category"])
        elif self.category and self.category != "general":
            self.metadata["category"] = self.category

        if "importance" in self.metadata and self.metadata["importance"]:
            try:
                self.importance = int(self.metadata["importance"])
            except (ValueError, TypeError):
                pass
        elif self.importance != 1:
            self.metadata["importance"] = self.importance

        if "source" in self.metadata and self.metadata["source"]:
            self.source = str(self.metadata["source"])
        elif self.source != "USER_EXPLICIT":
            self.metadata["source"] = self.source

        if "key" in self.metadata and self.metadata["key"]:
            self.key = str(self.metadata["key"])
        if "value" in self.metadata and self.metadata["value"]:
            self.value = str(self.metadata["value"])
        if "scope" in self.metadata and self.metadata["scope"]:
            self.scope = str(self.metadata["scope"])
        if "confidence" in self.metadata and self.metadata["confidence"]:
            self.confidence = str(self.metadata["confidence"])
        if "classification" in self.metadata and self.metadata["classification"]:
            self.classification = str(self.metadata["classification"])

        if "updated_at" in self.metadata and self.metadata["updated_at"]:
            self.updated_at = str(self.metadata["updated_at"])

        if not self.updated_at:
            self.updated_at = self.created_at


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
    def update(
        self,
        memory_id: str,
        content: str | None = None,
        metadata: dict[str, Any] | None = None,
        importance: int | None = None,
        category: str | None = None,
    ) -> MemoryEntry | None:
        """Update an existing memory item by ID."""

    @abstractmethod
    def list_all(self, limit: int = 100) -> list[MemoryEntry]:
        """List stored memories up to limit."""

    @abstractmethod
    def clear(self) -> None:
        """Clear all memories."""
