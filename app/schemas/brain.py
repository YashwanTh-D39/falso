from __future__ import annotations

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    """Single message in a conversation history."""
    role: str = Field(pattern=r"^(system|user|assistant)$")
    content: str


class ChatRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=50_000)
    history: list[ChatMessage] = Field(default_factory=list)

