from app.personality.base import Personality, PromptInput
from app.personality.core import assemble_core
from app.personality.registry import register_personality


@register_personality
class DefaultPersonality(Personality):
    id = "default"
    name = "Falso (Default)"
    description = "The stock FALSO assistant: friendly, concise, and direct."

    def build_prompt(self, pi: PromptInput) -> str:
        prompt = assemble_core(pi.core_prompt, pi.runtime_context)
        if pi.user_preferences.verbosity == "detailed":
            prompt += (
                "\n\nThe user prefers detailed responses. Elaborate with "
                "explanations and examples unless they ask for a short answer."
            )
        return prompt