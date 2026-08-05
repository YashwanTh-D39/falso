# Personality Engine — pure system-prompt assembly.
#
# This package is deliberately independent of the Conversation Engine
# (app/services/brain.py): it never routes tools, never calls the LLM, never
# touches memory, and contains no conversation logic. The Conversation Engine
# only ever asks PersonalityEngine.build_prompt(...) for the system prompt.
#
# Importing this package registers all built-in personalities (import-time
# side effect, same pattern as ToolRegistry).
from app.personality.base import (
    ConversationState,
    Personality,
    PromptInput,
    RuntimeContext,
    UserPreferences,
)
from app.personality.core import CORE_SYSTEM_PROMPT, assemble_core
from app.personality.engine import PersonalityEngine, PersonalityError
from app.personality.personalities import (
    DefaultPersonality,
    FriendlyPersonality,
    JarvisPersonality,
    MinimalPersonality,
    TechnicianPersonality,
    UltronPersonality,
)
from app.personality.registry import PersonalityRegistry, register_personality

__all__ = [
    "CORE_SYSTEM_PROMPT",
    "ConversationState",
    "DefaultPersonality",
    "FriendlyPersonality",
    "JarvisPersonality",
    "MinimalPersonality",
    "Personality",
    "PersonalityEngine",
    "PersonalityError",
    "PersonalityRegistry",
    "PromptInput",
    "RuntimeContext",
    "TechnicianPersonality",
    "UltronPersonality",
    "UserPreferences",
    "assemble_core",
    "register_personality",
]