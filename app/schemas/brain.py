from __future__ import annotations

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    """Single message in a conversation history."""
    role: str = Field(pattern=r"^(system|user|assistant)$")
    content: str


from typing import Optional

class ChatRequest(BaseModel):
    prompt: Optional[str] = Field(default=None, min_length=1, max_length=50_000)
    message: Optional[str] = Field(default=None, min_length=1, max_length=50_000)
    request_id: Optional[str] = Field(default=None)
    history: list[ChatMessage] = Field(default_factory=list)

    def get_prompt(self) -> str:
        p = self.prompt or self.message or ""
        if not p.strip():
            raise ValueError("Prompt or message cannot be empty")
        return p

