import json

import pytest

from app.providers import AIProviderError, ProviderChunk
from app.schemas.brain import ChatRequest
from app.services.brain import BrainService, BrainServiceError


class TestBrainServiceValidation:
    def setup_method(self) -> None:
        self.service = BrainService()

    def test_validate_prompt_rejects_empty(self) -> None:
        with pytest.raises(BrainServiceError, match="Prompt cannot be empty"):
            self.service.validate_prompt("")

    def test_validate_prompt_rejects_whitespace(self) -> None:
        with pytest.raises(BrainServiceError, match="Prompt cannot be empty"):
            self.service.validate_prompt("   \n\t  ")

    def test_validate_prompt_accepts_text(self) -> None:
        assert self.service.validate_prompt("hello") is None


class TestBrainServiceToolRouting:
    """Tool routing must work without any LLM or network."""

    def setup_method(self) -> None:
        self.service = BrainService()

    async def _events(self, prompt: str) -> list[dict]:
        return [json.loads(line) async for line in self.service.chat(prompt)]

    async def test_time_tool_routing(self) -> None:
        events = await self._events("what is the time now")
        assert events[0]["type"] == "tool_start"
        assert events[0]["tool"] == "time"
        last = events[-1]
        assert last["done"] is True
        assert last["model"] == self.service.model
        assert "Time" in last["response"]

    async def test_system_tool_routing(self) -> None:
        events = await self._events("tell me the cpu usage")
        assert events[0]["type"] == "tool_start"
        assert events[0]["tool"] == "system"
        assert events[-1]["done"] is True

    async def test_pending_requires_confirmation(self) -> None:
        # The file tool delete without "confirmed" stores a pending action
        # and must not hit the LLM (no network, no error).
        events = await self._events("delete notes.txt")
        assert events[-1]["done"] is True


class FakeProvider:
    """Minimal BaseAIProvider stand-in: scripted chunks or a scripted error.

    The Brain service must not care which vendor backs it, so these tests
    only verify the provider-agnostic behavior: chunk forwarding, the final
    done line, and error surfacing.
    """

    name = "fake"
    model = "fake-model"

    def __init__(self, chunks=None, error: Exception | None = None) -> None:
        self._chunks = chunks or [
            ProviderChunk(text="Hi "),
            ProviderChunk(text="there"),
        ]
        self._error = error
        self.messages: list[dict] | None = None

    async def stream_chat(self, messages: list[dict], **kwargs):
        self.messages = messages
        if self._error is not None:
            raise self._error
        for chunk in self._chunks:
            yield chunk


class TestBrainServiceLlmStreaming:
    """LLM streaming path with a mocked provider (no network anywhere)."""

    def setup_method(self) -> None:
        self.service = BrainService(provider=FakeProvider())

    def _inject(self, provider: FakeProvider) -> BrainService:
        return BrainService(provider=provider)

    async def _events(self, service: BrainService, prompt: str = "hello, no tool words here") -> list[dict]:
        return [json.loads(line) async for line in service.chat(prompt)]

    async def test_streams_assistant_chunks(self) -> None:
        events = await self._events(self.service)
        assert "".join(e.get("response", "") for e in events) == "Hi there"
        assert events[-1]["done"] is True
        assert events[0]["model"] == "fake-model"

    async def test_always_ends_with_done_line(self) -> None:
        provider = FakeProvider(chunks=[ProviderChunk(text="only chunk")])
        events = await self._events(self._inject(provider))
        assert events[-1]["done"] is True
        assert events[-1]["model"] == "fake-model"
        assert events[-1]["response"] == ""

    async def test_empty_chunks_skipped_but_done_emitted(self) -> None:
        provider = FakeProvider(chunks=[ProviderChunk(text="")])
        events = await self._events(self._inject(provider))
        assert len(events) == 1
        assert events[0]["done"] is True

    async def test_provider_error_yields_error_line(self) -> None:
        provider = FakeProvider(error=AIProviderError("OpenAI API key not configured"))
        events = await self._events(self._inject(provider))
        assert len(events) == 1
        assert "OpenAI API key not configured" in events[0]["error"]

    async def test_connect_error_yields_error_line(self) -> None:
        provider = FakeProvider(error=AIProviderError("OpenAI connection failed: refused"))
        events = await self._events(self._inject(provider))
        assert len(events) == 1
        assert "OpenAI connection failed" in events[0]["error"]

    async def test_unexpected_error_yields_error_line(self) -> None:
        provider = FakeProvider(error=RuntimeError("boom"))
        events = await self._events(self._inject(provider))
        assert len(events) == 1
        assert events[0]["error"] == "fake error: boom"


class StubPersonalityEngine:
    def __init__(self, prompt: str = "STUB-PROMPT") -> None:
        self._prompt = prompt

    def build_prompt(self, **kwargs) -> str:
        return self._prompt


class TestBrainServicePersonalityInjection:
    """The Conversation Engine must get its system prompt only from the
    injected PersonalityEngine — one abstraction, nothing else."""

    def setup_method(self) -> None:
        self.service = BrainService(
            personality_engine=StubPersonalityEngine(),
            provider=FakeProvider(chunks=[ProviderChunk(text="Hi", done=True)]),
        )

    async def test_injected_engine_prompt_used_in_provider_request(self) -> None:
        events = [
            json.loads(line)
            async for line in self.service.chat("hello, no tool words here")
        ]
        assert events[-1]["done"] is True

        messages = self.service.provider.messages
        assert messages[0]["role"] == "system"
        assert messages[0]["content"].startswith("STUB-PROMPT")
        assert messages[1] == {
            "role": "user",
            "content": "hello, no tool words here",
        }

    async def test_injected_engine_receives_runtime_context(self) -> None:
        captured = {}

        class CapturingEngine(StubPersonalityEngine):
            def build_prompt(self, **kwargs) -> str:
                captured.update(kwargs)
                return super().build_prompt(**kwargs)

        service = BrainService(
            personality_engine=CapturingEngine(),
            provider=FakeProvider(),
        )
        _ = [
            json.loads(line)
            async for line in service.chat("hello, no tool words here")
        ]

        assert captured["runtime_context"].model == service.model  # "fake-model"
        assert set(captured["runtime_context"].capabilities) >= {"time", "system", "file"}
        assert captured["conversation_state"].last_filename is None

    def test_default_brain_service_builds_prompt_via_personality_engine(self) -> None:
        service = BrainService(provider=FakeProvider())
        prompt = service.personality_engine.build_prompt()
        assert "FALSO" in prompt


class TestChatRequestModel:
    def test_accepts_valid_prompt(self) -> None:
        request = ChatRequest(prompt="test prompt")
        assert request.prompt == "test prompt"

    def test_rejects_empty_prompt(self) -> None:
        with pytest.raises(ValueError):
            ChatRequest(prompt="")

    def test_rejects_oversized_prompt(self) -> None:
        with pytest.raises(ValueError):
            ChatRequest(prompt="a" * 50_001)
