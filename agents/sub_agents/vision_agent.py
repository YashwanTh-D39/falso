from __future__ import annotations

import logging
from typing import Any

from agents.base import AgentResult, BaseSubAgent
from agents.registry import AgentRegistry
from vision import VisionService

logger = logging.getLogger(__name__)


@AgentRegistry.register
class VisionAgent(BaseSubAgent):
    name = "vision"
    role = "Visual Analysis & OCR Specialist Agent"
    description = "Analyzes image frames, extracts visual structure, and performs OCR text extraction."

    def __init__(self, service: VisionService | None = None) -> None:
        self.service = service or VisionService()

    async def run(self, prompt: str, **kwargs: Any) -> AgentResult:
        logger.info("VisionAgent processing visual request: %r", prompt[:60])
        response = f"[Vision Agent] Processed visual analysis query: '{prompt}'."

        return AgentResult(
            agent_name=self.name,
            response=response,
            metadata={"type": "vision_analysis"},
        )
