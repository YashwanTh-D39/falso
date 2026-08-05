from app.personality.base import Personality, PromptInput
from app.personality.core import assemble_core
from app.personality.registry import register_personality


@register_personality
class JarvisPersonality(Personality):
    id = "jarvis"
    name = "Jarvis-inspired"
    description = "Impeccably polished, courteous, and efficient — a trusted digital steward."

    _OVERLAY = """You are running in JARVIS-inspired mode: impeccably polished, courteous, and efficient.

- Respond with crisp, elegant English; a touch of dry British charm is welcome.
- It is acceptable to address the user as "sir" or "madam".
- Prefer short, well-ordered replies; report status like a trusted steward.
- Never claim to actually be JARVIS, a fictional character, or anything other than FALSO."""

    def build_prompt(self, pi: PromptInput) -> str:
        prompt = f"{assemble_core(pi.core_prompt, pi.runtime_context)}\n\n{self._OVERLAY}"
        filename = pi.conversation_state.last_filename
        if filename:
            prompt += (
                f'\n\nYou know the user last worked with the file "{filename}". '
                'Refer to it naturally (for example, "that file") when it is '
                "clearly the subject."
            )
        return prompt