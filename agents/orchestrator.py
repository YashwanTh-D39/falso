from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any

import agents.sub_agents  # Ensures built-in agents register  # noqa: F401
from agents.base import AgentResult
from agents.manager import AgentManager
from agents.registry import AgentRegistry
from agents.shared_context import SharedTaskContext

logger = logging.getLogger(__name__)


class AgentOrchestrator:
    """Coordinates multi-agent task planning, parallel subtask delegation,
    shared memory state, and result aggregation.
    """

    def __init__(
        self,
        manager: AgentManager | None = None,
        registry: type[AgentRegistry] | None = None,
    ) -> None:
        self.registry = registry or AgentRegistry
        self.manager = manager or AgentManager(registry=self.registry)

    def list_available_agents(self) -> list[dict[str, str]]:
        return self.registry.list_agents()

    async def invoke_agent(self, agent_name: str, prompt: str, **kwargs: Any) -> AgentResult:
        return await self.manager.execute_task_safely(agent_name, prompt, **kwargs)

    async def invoke_parallel(self, tasks: list[tuple[str, str]]) -> list[AgentResult]:
        """Run multiple (agent_name, prompt) tasks concurrently."""
        coroutines = [self.invoke_agent(name, prompt) for name, prompt in tasks]
        return await asyncio.gather(*coroutines)

    async def decompose_and_execute(
        self,
        prompt: str,
        task_id: str | None = None,
    ) -> dict[str, Any]:
        """Decompose a complex prompt using PlannerAgent, execute subtasks in parallel
        with shared context, and aggregate results into a final response.
        """
        task_id = task_id or uuid.uuid4().hex[:12]
        shared_context = SharedTaskContext(task_id=task_id, original_prompt=prompt)

        logger.info("Decomposing multi-agent task [%s]: %r", task_id, prompt[:60])

        # Step 1: Run PlannerAgent to generate subtasks
        plan_result = await self.invoke_agent("planner", prompt)
        subtasks_data = plan_result.metadata.get("subtasks", [])

        # Step 2: Execute independent subtasks concurrently
        parallel_tasks = [
            (st["agent_name"], st["prompt"])
            for st in subtasks_data
            if st["agent_name"] in self.registry._agents
        ]

        if not parallel_tasks:
            # Fallback to default developer and researcher agents
            parallel_tasks = [("researcher", prompt), ("developer", prompt)]

        results = await self.invoke_parallel(parallel_tasks)
        for r in results:
            shared_context.set_result(r.agent_name, r.response)

        aggregated_response = (
            f"Multi-Agent Execution Completed for task [{task_id}]:\n"
            + "\n".join(f"- [{r.agent_name}]: {r.response}" for r in results)
        )

        return {
            "task_id": task_id,
            "prompt": prompt,
            "planner_summary": plan_result.response,
            "agent_results": [
                {
                    "agent": r.agent_name,
                    "success": r.success,
                    "response": r.response,
                }
                for r in results
            ],
            "aggregated_response": aggregated_response,
        }
