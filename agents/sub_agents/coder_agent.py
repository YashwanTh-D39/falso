from __future__ import annotations

import logging
from typing import Any

from agents.base import AgentResult, BaseSubAgent
from agents.registry import AgentRegistry

logger = logging.getLogger(__name__)


@AgentRegistry.register
class CoderAgent(BaseSubAgent):
    name = "coder"
    role = "Software Development Assistant"
    description = "Generates, reviews, and refactors code structures."

    async def run(self, prompt: str, **kwargs: Any) -> AgentResult:
        logger.info("CoderAgent executing prompt: %r", prompt[:60])
        response = f"[Code Generation] Solution drafted for: '{prompt}'."
        return AgentResult(
            agent_name=self.name,
            response=response,
            metadata={"query": prompt, "type": "coding"},
        )
