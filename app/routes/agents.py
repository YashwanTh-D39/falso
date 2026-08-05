from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from agents import AgentOrchestrator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/agents", tags=["Agents"])
orchestrator = AgentOrchestrator()


class AgentExecuteRequest(BaseModel):
    agent_name: str = Field(min_length=1)
    prompt: str = Field(min_length=1, max_length=10_000)


class DecomposeRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=10_000)


@router.get("/")
async def list_agents():
    return orchestrator.list_available_agents()


@router.post("/execute")
async def execute_agent(request: AgentExecuteRequest):
    result = await orchestrator.invoke_agent(request.agent_name, request.prompt)
    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.response,
        )
    return {
        "agent": result.agent_name,
        "task_id": result.task_id,
        "response": result.response,
        "metadata": result.metadata,
        "timestamp": result.timestamp,
    }


@router.post("/decompose")
async def decompose_and_execute(request: DecomposeRequest):
    return await orchestrator.decompose_and_execute(request.prompt)
