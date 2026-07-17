from datetime import datetime, timezone

from pydantic import BaseModel


class ChatRequest(BaseModel):
    prompt: str


class ChatResponse(BaseModel):
    response: str
    model: str
    timestamp: str = datetime.now(timezone.utc).isoformat()
