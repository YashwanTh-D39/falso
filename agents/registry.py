from __future__ import annotations

import logging
from typing import ClassVar

from agents.base import BaseSubAgent

logger = logging.getLogger(__name__)


class AgentRegistry:
    """Registry of available sub-agent types."""

    _agents: ClassVar[dict[str, type[BaseSubAgent]]] = {}

    @classmethod
    def register(cls, agent_cls: type[BaseSubAgent]) -> type[BaseSubAgent]:
        name = getattr(agent_cls, "name", agent_cls.__name__).lower()
        cls._agents[name] = agent_cls
        logger.debug("Registered sub-agent: %s", name)
        return agent_cls

    @classmethod
    def get(cls, name: str) -> type[BaseSubAgent] | None:
        return cls._agents.get(name.lower())

    @classmethod
    def list_agents(cls) -> list[dict[str, str]]:
        result = []
        for name, agent_cls in cls._agents.items():
            result.append({
                "name": name,
                "role": getattr(agent_cls, "role", "Sub-agent"),
                "description": getattr(agent_cls, "description", ""),
            })
        return result
