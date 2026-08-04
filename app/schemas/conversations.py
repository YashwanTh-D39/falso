
from pydantic import BaseModel, Field


class Message(BaseModel):
    role: str = Field(max_length=32)
    text: str = Field(max_length=200_000)
    time: str = Field(max_length=64)


class Conversation(BaseModel):
    id: str = Field(min_length=1, max_length=64)
    title: str = Field(default="New Chat", max_length=200)
    messages: list[Message] = Field(default_factory=list)
    createdAt: str = Field(default="", max_length=64)
    updatedAt: str = Field(default="", max_length=64)
