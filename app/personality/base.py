from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import ClassVar


@dataclass(frozen=True)
class UserPreferences:
    language: str = "English"
    verbosity: str = "concise"
    formality: str = "friendly"


@dataclass(frozen=True)
class RuntimeContext:
    model: str = ""
    capabilities: tuple[str, ...] = ()


@dataclass(frozen=True)
class ConversationState:
    last_filename: str | None = None
    pending_tool: str | None = None
    pending_intent: str | None = None


@dataclass(frozen=True)
class PromptInput:
    core_prompt: str
    user_preferences: UserPreferences
    runtime_context: RuntimeContext
    conversation_state: ConversationState


class Personality(ABC):
    id: ClassVar[str]
    name: ClassVar[str]
    description: ClassVar[str]

    @abstractmethod
    def build_prompt(self, pi: PromptInput) -> str:
        """Render the full system prompt for this personality.

        Pure prompt assembly: no LLM calls, no memory access, no tool routing,
        no conversation orchestration.
        """
