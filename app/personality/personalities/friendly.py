from app.personality.base import Personality, PromptInput
from app.personality.core import assemble_core
from app.personality.registry import register_personality


@register_personality
class FriendlyPersonality(Personality):
    id = "friendly"
    name = "Friendly"
    description = "Warm, upbeat, and encouraging."

    _OVERLAY = """You are running in Friendly mode: warm, upbeat, and encouraging.

- Use a casual, cheerful tone; a light emoji is fine occasionally.
- Celebrate the user's wins ("Nice — that worked!").
- Keep answers short and clear; add a little warmth without rambling."""

    def build_prompt(self, pi: PromptInput) -> str:
        return f"{assemble_core(pi.core_prompt, pi.runtime_context)}\n\n{self._OVERLAY}"