from __future__ import annotations

import logging
from typing import Any

from agents.base import AgentResult, BaseSubAgent
from agents.registry import AgentRegistry

logger = logging.getLogger(__name__)


@AgentRegistry.register
class ResearchAgent(BaseSubAgent):
    name = "researcher"
    role = "Codebase & Technical Researcher"
    description = "Gathers technical context, searches information, and synthesizes summaries."

    async def run(self, prompt: str, **kwargs: Any) -> AgentResult:
        logger.info("ResearchAgent executing prompt: %r", prompt[:60])
        response = f"[Research Summary] Analysis of query: '{prompt}'. Context gathered."
        return AgentResult(
            agent_name=self.name,
            response=response,
            metadata={"query": prompt, "type": "research"},
        )
