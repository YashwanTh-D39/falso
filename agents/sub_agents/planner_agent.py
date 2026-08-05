from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from agents.base import AgentResult, BaseSubAgent
from agents.registry import AgentRegistry

logger = logging.getLogger(__name__)


@dataclass
class SubTask:
    id: str
    agent_name: str
    prompt: str
    dependencies: list[str] = field(default_factory=list)


@AgentRegistry.register
class PlannerAgent(BaseSubAgent):
    name = "planner"
    role = "Task Planner & Decomposition Engine"
    description = "Decomposes complex multi-step user prompts into parallel or sequential subtasks."

    async def run(self, prompt: str, **kwargs: Any) -> AgentResult:
        logger.info("PlannerAgent decomposing prompt: %r", prompt[:60])

        # Subtask decomposition logic
        subtasks = [
            SubTask(id="st_1", agent_name="researcher", prompt=f"Research context for: {prompt}"),
            SubTask(id="st_2", agent_name="developer", prompt=f"Develop implementation plan for: {prompt}", dependencies=["st_1"]),
        ]

        summary = f"[Plan Generated] 2 subtasks decomposed for query: '{prompt}'"
        return AgentResult(
            agent_name=self.name,
            response=summary,
            metadata={
                "subtasks": [
                    {
                        "id": st.id,
                        "agent_name": st.agent_name,
                        "prompt": st.prompt,
                        "dependencies": st.dependencies,
                    }
                    for st in subtasks
                ]
            },
        )
