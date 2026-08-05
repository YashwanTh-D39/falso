from app.personality import (
    ConversationState,
    Personality,
    PersonalityEngine,
    PersonalityRegistry,
    PromptInput,
    RuntimeContext,
    UserPreferences,
)

BUILTIN_IDS = {"default", "technician", "ultron", "jarvis", "minimal", "friendly"}


class TestPersonalityRegistry:
    def test_all_builtin_personalities_registered(self) -> None:
        ids = {p["id"] for p in PersonalityRegistry.list()}
        assert BUILTIN_IDS.issubset(ids)

    def test_get_known_and_unknown(self) -> None:
        assert PersonalityRegistry.get("technician") is not None
        assert PersonalityRegistry.get("does-not-exist") is None

    def test_custom_personality_can_be_registered(self) -> None:
        class CustomPersonality(Personality):
            id = "custom-test"
            name = "Custom"
            description = "Test personality"

            def build_prompt(self, pi: PromptInput) -> str:
                return f"CUSTOM {pi.core_prompt}"

        PersonalityRegistry.register(CustomPersonality)
        try:
            engine = PersonalityEngine(core_prompt="CORE")
            assert engine.build_prompt(personality="custom-test") == "CUSTOM CORE"
            assert "custom-test" in {p["id"] for p in engine.available_personalities}
        finally:
            PersonalityRegistry._personalities.pop("custom-test", None)


class TestPersonalityEngine:
    def test_default_prompt_buildable_without_arguments(self) -> None:
        engine = PersonalityEngine()
        prompt = engine.build_prompt()
        assert prompt.strip()
        assert "FALSO" in prompt

    def test_every_personality_is_distinct_and_identifies_as_falso(self) -> None:
        engine = PersonalityEngine()
        prompts = {pid: engine.build_prompt(personality=pid) for pid in BUILTIN_IDS}
        assert len(set(prompts.values())) == len(BUILTIN_IDS)
        for pid, prompt in prompts.items():
            assert "FALSO" in prompt, pid

    def test_unknown_personality_falls_back_to_default(self) -> None:
        engine = PersonalityEngine()
        assert engine.build_prompt(personality="does-not-exist") == engine.build_prompt(
            personality="default"
        )

    def test_injected_core_prompt_used_verbatim(self) -> None:
        engine = PersonalityEngine(core_prompt="CUSTOM CORE")
        assert engine.build_prompt().startswith("CUSTOM CORE")

    def test_builtin_core_renders_runtime_capabilities(self) -> None:
        engine = PersonalityEngine()
        prompt = engine.build_prompt(
            runtime_context=RuntimeContext(capabilities=("time", "system"))
        )
        assert "- Time tool —" in prompt
        assert "- System tool —" in prompt
        assert "- File tool —" not in prompt

    def test_builtin_core_renders_runtime_model(self) -> None:
        engine = PersonalityEngine()
        prompt = engine.build_prompt(runtime_context=RuntimeContext(model="llama3:8b"))
        assert "llama3:8b" in prompt

    def test_empty_capabilities_rendered_gracefully(self) -> None:
        engine = PersonalityEngine()
        prompt = engine.build_prompt(runtime_context=RuntimeContext())
        assert "No local tools are currently registered" in prompt

    def test_verbosity_detailed_appends_directive(self) -> None:
        engine = PersonalityEngine()
        base = engine.build_prompt(personality="default")
        detailed = engine.build_prompt(
            personality="default",
            user_preferences=UserPreferences(verbosity="detailed"),
        )
        assert "prefers detailed responses" in detailed
        assert "prefers detailed responses" not in base

    def test_language_preference_appended(self) -> None:
        engine = PersonalityEngine()
        prompt = engine.build_prompt(
            personality="default", user_preferences=UserPreferences(language="Spanish")
        )
        assert "prefers to communicate in Spanish" in prompt

    def test_formality_preference_appended(self) -> None:
        engine = PersonalityEngine()
        prompt = engine.build_prompt(
            personality="minimal", user_preferences=UserPreferences(formality="formal")
        )
        assert "formal language" in prompt

    def test_constructor_level_preferences_apply_to_build(self) -> None:
        engine = PersonalityEngine(user_preferences=UserPreferences(language="German"))
        assert "prefers to communicate in German" in engine.build_prompt()

    def test_conversation_state_shapes_jarvis_prompt(self) -> None:
        engine = PersonalityEngine()
        plain = engine.build_prompt(personality="jarvis")
        aware = engine.build_prompt(
            personality="jarvis",
            conversation_state=ConversationState(last_filename="notes.txt"),
        )
        assert 'last worked with the file "notes.txt"' in aware
        assert "notes.txt" not in plain

    def test_conversation_state_ignored_by_default_personality(self) -> None:
        engine = PersonalityEngine()
        prompt = engine.build_prompt(
            personality="default",
            conversation_state=ConversationState(last_filename="notes.txt"),
        )
        assert "notes.txt" not in prompt

    def test_pending_state_flows_through_without_effect(self) -> None:
        engine = PersonalityEngine()
        prompt = engine.build_prompt(
            conversation_state=ConversationState(
                pending_tool="file", pending_intent="delete"
            ),
        )
        assert "FALSO" in prompt