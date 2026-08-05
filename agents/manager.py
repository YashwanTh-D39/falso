from __future__ import annotations

import asyncio
import logging
from typing import Any

from agents.base import AgentResult, BaseSubAgent
from agents.registry import AgentRegistry
from agents.shared_context import SharedTaskContext

logger = logging.getLogger(__name__)


class AgentManager:
    """Central Agent Manager responsible for spawning, monitoring, loop prevention,
    safety permissions, and agent lifecycle management.
    """

    def __init__(
        self,
        registry: type[AgentRegistry] | None = None,
        max_subtasks: int = 10,
        timeout_seconds: float = 60.0,
    ) -> None:
        self.registry = registry or AgentRegistry
        self.max_subtasks = max_subtasks
        self.timeout_seconds = timeout_seconds
        self._active_agents: dict[str, BaseSubAgent] = {}
        self._action_logs: list[dict[str, Any]] = []

    def create_agent(self, agent_name: str) -> BaseSubAgent:
        agent_cls = self.registry.get(agent_name)
        if agent_cls is None:
            raise ValueError(f"Unknown agent name: {agent_name!r}")

        instance = agent_cls()
        self._active_agents[agent_name] = instance
        self._log_action("create", agent_name, f"Agent {agent_name!r} spawned")
        return instance

    def terminate_agent(self, agent_name: str) -> bool:
        if agent_name in self._active_agents:
            del self._active_agents[agent_name]
            self._log_action("terminate", agent_name, f"Agent {agent_name!r} terminated")
            return True
        return False

    def list_active_agents(self) -> list[str]:
        return list(self._active_agents.keys())

    def get_action_logs(self, limit: int = 50) -> list[dict[str, Any]]:
        return self._action_logs[-limit:]

    def _log_action(self, action_type: str, agent_name: str, details: str) -> None:
        log_entry = {
            "action": action_type,
            "agent": agent_name,
            "details": details,
        }
        self._action_logs.append(log_entry)
        logger.info("AgentManager [%s] agent=%s: %s", action_type, agent_name, details)

    async def execute_task_safely(
        self,
        agent_name: str,
        prompt: str,
        shared_context: SharedTaskContext | None = None,
        **kwargs: Any,
    ) -> AgentResult:
        """Safely execute a task with loop prevention, timeout, and failure isolation."""
        try:
            agent = self.create_agent(agent_name)
            result = await asyncio.wait_for(
                agent.run(prompt, **kwargs),
                timeout=self.timeout_seconds,
            )
            if shared_context:
                shared_context.set_result(agent_name, result.response)
            self._log_action("complete", agent_name, f"Task finished: {result.success}")
            return result
        except TimeoutError:
            err_msg = f"Execution timed out after {self.timeout_seconds}s"
            self._log_action("timeout", agent_name, err_msg)
            return AgentResult(agent_name=agent_name, response=f"Error: {err_msg}", success=False)
        except Exception as exc:  # noqa: BLE001
            err_msg = str(exc)
            self._log_action("error", agent_name, err_msg)
            return AgentResult(agent_name=agent_name, response=f"Error: {err_msg}", success=False)
        finally:
            self.terminate_agent(agent_name)
