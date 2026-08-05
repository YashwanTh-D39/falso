from __future__ import annotations

import logging
from typing import Any

from agents.base import AgentResult, BaseSubAgent
from agents.registry import AgentRegistry

logger = logging.getLogger(__name__)


@AgentRegistry.register
class AnalystAgent(BaseSubAgent):
    name = "analyst"
    role = "Data & System Metrics Analyst"
    description = "Analyzes performance metrics, logs, and structured datasets."

    async def run(self, prompt: str, **kwargs: Any) -> AgentResult:
        logger.info("AnalystAgent executing prompt: %r", prompt[:60])
        response = f"[Metrics Analysis] Diagnostic completed for: '{prompt}'."
        return AgentResult(
            agent_name=self.name,
            response=response,
            metadata={"query": prompt, "type": "analysis"},
        )
