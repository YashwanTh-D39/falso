from __future__ import annotations

import logging
from typing import Any

from agents.base import AgentResult, BaseSubAgent
from agents.registry import AgentRegistry
from automation import AutomationEngine

logger = logging.getLogger(__name__)


@AgentRegistry.register
class AutomationAgent(BaseSubAgent):
    name = "automation"
    role = "Task Automation Specialist Agent"
    description = "Schedules, executes, and monitors automated background jobs and workflows."

    def __init__(self, engine: AutomationEngine | None = None) -> None:
        self.engine = engine or AutomationEngine()

    async def run(self, prompt: str, **kwargs: Any) -> AgentResult:
        logger.info("AutomationAgent executing task: %r", prompt[:60])
        tasks = self.engine.list_tasks()
        response = f"[Automation Agent] Managed task loop executed for: '{prompt}'. Active jobs={len(tasks)}"

        return AgentResult(
            agent_name=self.name,
            response=response,
            metadata={"active_jobs_count": len(tasks)},
        )
