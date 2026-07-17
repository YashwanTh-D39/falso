from pydantic import BaseModel
from typing import List


class Message(BaseModel):
    role: str
    text: str
    time: str


class Conversation(BaseModel):
    id: str
    title: str = "New Chat"
    messages: List[Message] = []
    createdAt: str = ""
    updatedAt: str = ""
