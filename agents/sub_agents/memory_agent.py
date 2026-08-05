from __future__ import annotations

import logging
from typing import Any

from agents.base import AgentResult, BaseSubAgent
from agents.registry import AgentRegistry
from memory import MemoryService

logger = logging.getLogger(__name__)


@AgentRegistry.register
class MemoryAgent(BaseSubAgent):
    name = "memory"
    role = "Long-Term Memory Specialist Agent"
    description = "Searches, extracts, stores, and organizes cross-session long-term memories."

    def __init__(self, memory_service: MemoryService | None = None) -> None:
        self.memory_service = memory_service or MemoryService()

    async def run(self, prompt: str, **kwargs: Any) -> AgentResult:
        logger.info("MemoryAgent executing query: %r", prompt[:60])
        summary = self.memory_service.get_context_summary(prompt, limit=3)
        if not summary:
            summary = f"No prior memories found for: '{prompt}'"

        return AgentResult(
            agent_name=self.name,
            response=f"[Memory Agent] {summary}",
            metadata={"type": "memory_recall"},
        )
