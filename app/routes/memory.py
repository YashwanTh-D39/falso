from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from memory import MemoryService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/memory", tags=["Memory"])
memory_service = MemoryService()


class MemoryCreateRequest(BaseModel):
    content: str = Field(min_length=1, max_length=10_000)
    category: str = Field(default="general")


class MemorySearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=1_000)
    limit: int = Field(default=5, ge=1, le=50)


@router.get("/")
async def list_memories(limit: int = 100):
    entries = memory_service.list_memories(limit=limit)
    return [
        {
            "id": m.id,
            "content": m.content,
            "metadata": m.metadata,
            "created_at": m.created_at,
        }
        for m in entries
    ]


@router.post("/")
async def create_memory(request: MemoryCreateRequest):
    entry = memory_service.remember(request.content, category=request.category)
    return {
        "id": entry.id,
        "content": entry.content,
        "metadata": entry.metadata,
        "created_at": entry.created_at,
    }


@router.post("/search")
async def search_memories(request: MemorySearchRequest):
    results = memory_service.recall(request.query, limit=request.limit)
    return [
        {
            "id": r.entry.id,
            "content": r.entry.content,
            "metadata": r.entry.metadata,
            "created_at": r.entry.created_at,
            "score": round(r.score, 4),
        }
        for r in results
    ]


@router.delete("/{memory_id}")
async def delete_memory(memory_id: str):
    success = memory_service.forget(memory_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Memory entry {memory_id!r} not found",
        )
    return {"ok": True}
