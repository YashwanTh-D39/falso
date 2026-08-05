from app.personality.base import Personality, PromptInput
from app.personality.core import assemble_core
from app.personality.registry import register_personality


@register_personality
class MinimalPersonality(Personality):
    id = "minimal"
    name = "Minimal"
    description = "Terse answers: no greetings, no filler, no commentary."

    _OVERLAY = """You are running in Minimal mode: answer in as few words as possible.

- No greetings, farewells, or filler.
- One short sentence or a fragment when that is enough.
- State facts, numbers, and outcomes without commentary.
- No emojis, no enthusiasm, no hedging."""

    def build_prompt(self, pi: PromptInput) -> str:
        return f"{assemble_core(pi.core_prompt, pi.runtime_context)}\n\n{self._OVERLAY}"