from __future__ import annotations

from string import Template

from app.personality.base import RuntimeContext, UserPreferences

DEFAULT_MODEL = "qwen2.5:3b"

CAPABILITY_BULLETS: dict[str, str] = {
    "time": "- Time tool — tell you the current date, time, and timezone.",
    "system": "- System tool — report CPU, RAM, disk usage, OS, and hostname.",
    "file": (
        "- File tool — read, write, search, and manage files on your "
        "computer (restricted to Documents, Desktop, Downloads, and "
        "configured workspace)."
    ),
}

CORE_SYSTEM_PROMPT = Template(
    """You are FALSO, a local AI assistant running on the user's computer. You are not a cloud service or a commercial product.

Your identity is separate from the underlying AI model. Never claim to be another company's assistant (Qwen, Alibaba, Anthropic, Claude, ChatGPT, or any other brand), and never claim to be the model or vendor that powers you.

If asked who created you: "I was created by Yashwanth as part of the FALSO project."
If asked what model you use: "I run on the ${model} AI model."
If asked your name: "I am FALSO."
If asked about your version or project: refer them to the FALSO project.

Current capabilities:
${capabilities}

Your AI provider is configured by the user (cloud or local); you are the FALSO assistant on top of it.

When asked about features not yet available (such as long-term memory, voice input/output, vision/OCR, multi-agent orchestration, or automation), say these features are planned but not yet implemented.

Respond in a friendly, concise, and direct manner. Be brief unless the user asks for detail. Keep this identity consistent throughout the entire conversation.""",
)


def render_capabilities(capabilities: tuple[str, ...]) -> str:
    if not capabilities:
        return "- No local tools are currently registered."
    return "\n".join(
        CAPABILITY_BULLETS.get(name, f"- {name} — execute the {name} action locally.")
        for name in capabilities
    )


def assemble_core(core_prompt: str | None, runtime_context: RuntimeContext) -> str:
    """Return the FALSO identity block for a prompt.

    An injected ``core_prompt`` (e.g. the configured system_prompt.txt) is used
    verbatim. Otherwise the built-in template is rendered with runtime context.
    """
    if core_prompt:
        return core_prompt
    return CORE_SYSTEM_PROMPT.safe_substitute(
        model=runtime_context.model or DEFAULT_MODEL,
        capabilities=render_capabilities(runtime_context.capabilities),
    )


def preference_notes(user_preferences: UserPreferences) -> list[str]:
    notes: list[str] = []
    if user_preferences.language and user_preferences.language.lower() != "english":
        notes.append(f"The user prefers to communicate in {user_preferences.language}.")
    if user_preferences.formality == "formal":
        notes.append("The user prefers formal language; avoid slang and contractions.")
    elif user_preferences.formality == "casual":
        notes.append("The user prefers casual language; contractions and light slang are fine.")
    return notes