from __future__ import annotations

import logging
from typing import Any

from agents.base import AgentResult, BaseSubAgent
from agents.registry import AgentRegistry

logger = logging.getLogger(__name__)


@AgentRegistry.register
class DeveloperAgent(BaseSubAgent):
    name = "developer"
    role = "Senior Software Developer Agent"
    description = "Writes, reviews, refactors code, and verifies system implementations."

    async def run(self, prompt: str, **kwargs: Any) -> AgentResult:
        logger.info("DeveloperAgent executing task: %r", prompt[:60])
        response = f"[Developer Agent] Solution and code implementation generated for: '{prompt}'."
        return AgentResult(
            agent_name=self.name,
            response=response,
            metadata={"type": "development", "status": "completed"},
        )
