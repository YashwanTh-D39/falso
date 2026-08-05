from __future__ import annotations

import asyncio
import logging
from typing import Any

import agents.sub_agents  # Ensures built-in agents register  # noqa: F401
from agents.base import AgentResult
from agents.registry import AgentRegistry

logger = logging.getLogger(__name__)


class AgentOrchestrator:
    """Coordinates sub-agent spawning, execution, and output aggregation."""

    def __init__(self, registry: type[AgentRegistry] | None = None) -> None:
        self.registry = registry or AgentRegistry

    def list_available_agents(self) -> list[dict[str, str]]:
        return self.registry.list_agents()

    async def invoke_agent(self, agent_name: str, prompt: str, **kwargs: Any) -> AgentResult:
        agent_cls = self.registry.get(agent_name)
        if agent_cls is None:
            logger.error("Requested unknown sub-agent: %r", agent_name)
            return AgentResult(
                agent_name=agent_name,
                response=f"Error: Unknown agent {agent_name!r}",
                success=False,
            )

        agent_instance = agent_cls()
        logger.info("Invoking sub-agent %r for task", agent_name)
        return await agent_instance.run(prompt, **kwargs)

    async def invoke_parallel(self, tasks: list[tuple[str, str]]) -> list[AgentResult]:
        """Run multiple (agent_name, prompt) tasks concurrently."""
        coroutines = [self.invoke_agent(name, prompt) for name, prompt in tasks]
        return await asyncio.gather(*coroutines)
