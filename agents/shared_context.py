from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from memory import MemoryService

logger = logging.getLogger(__name__)


@dataclass
class SharedTaskContext:
    """Shared state and context container for multi-agent task execution,
    integrated with long-term MemoryService.
    """

    task_id: str
    original_prompt: str
    memory_service: MemoryService = field(default_factory=MemoryService)
    results: dict[str, Any] = field(default_factory=dict)
    state: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(
        default_factory=lambda: datetime.now(UTC).isoformat()
    )

    def set_result(self, agent_name: str, output: Any) -> None:
        self.results[agent_name] = output
        logger.debug("Task [%s] Agent [%s] stored result", self.task_id, agent_name)

    def get_result(self, agent_name: str) -> Any | None:
        return self.results.get(agent_name)

    def remember_fact(self, fact: str, category: str = "agent_shared") -> None:
        self.memory_service.remember(fact, category=category)

    def recall_context(self, query: str, limit: int = 3) -> str:
        return self.memory_service.get_context_summary(query, limit=limit)
