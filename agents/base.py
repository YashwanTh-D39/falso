from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass
class AgentResult:
    agent_name: str
    response: str
    task_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    success: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(
        default_factory=lambda: datetime.now(UTC).isoformat()
    )


class BaseSubAgent(ABC):
    """Abstract base class for autonomous sub-agents."""

    name: str
    role: str
    description: str

    @abstractmethod
    async def run(self, prompt: str, **kwargs: Any) -> AgentResult:
        """Execute the sub-agent's task."""
