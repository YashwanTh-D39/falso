from __future__ import annotations

from app.personality.base import (
    ConversationState,
    PromptInput,
    RuntimeContext,
    UserPreferences,
)
from app.personality.core import preference_notes
from app.personality.registry import PersonalityRegistry

DEFAULT_PERSONALITY_ID = "default"


class PersonalityError(Exception):
    pass


class PersonalityEngine:
    """The only way the Conversation Engine obtains a system prompt.

    Pure and synchronous: no LLM calls, no memory management, no tool routing.
    Produces a system prompt purely from the selected personality plus user
    preferences, runtime context, and the current conversation state.
    """

    def __init__(
        self,
        *,
        registry: type[PersonalityRegistry] | None = None,
        default_personality: str = DEFAULT_PERSONALITY_ID,
        core_prompt: str | None = None,
        user_preferences: UserPreferences | None = None,
        runtime_context: RuntimeContext | None = None,
    ) -> None:
        self._registry = registry if registry is not None else PersonalityRegistry
        self.default_personality = default_personality or DEFAULT_PERSONALITY_ID
        self._core_prompt = core_prompt
        self._user_preferences = user_preferences or UserPreferences()
        self._runtime_context = runtime_context

    @property
    def available_personalities(self) -> list[dict[str, str]]:
        return self._registry.list()

    def build_prompt(
        self,
        *,
        personality: str | None = None,
        user_preferences: UserPreferences | None = None,
        runtime_context: RuntimeContext | None = None,
        conversation_state: ConversationState | None = None,
    ) -> str:
        requested = (
            personality or self.default_personality or DEFAULT_PERSONALITY_ID
        ).strip().lower()
        personality_cls = self._registry.get(requested) or self._registry.get(
            DEFAULT_PERSONALITY_ID
        )
        if personality_cls is None:
            raise PersonalityError(
                f"No personality named {requested!r} and no default registered"
            )

        pi = PromptInput(
            core_prompt=self._core_prompt,
            user_preferences=user_preferences or self._user_preferences,
            runtime_context=runtime_context or self._runtime_context or RuntimeContext(),
            conversation_state=conversation_state or ConversationState(),
        )
        prompt = personality_cls().build_prompt(pi)

        notes = preference_notes(pi.user_preferences)
        if notes:
            prompt = f"{prompt}\n\n" + "\n".join(notes)

        return prompt