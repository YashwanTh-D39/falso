"""Provider layer tests — the only place vendor HTTP is mocked.

These prove the transport/translation contract each provider implements
(OpenAI-style messages -> vendor request, delta/NDJSON parsing, error
surfacing, lazy client) without touching the network.
"""

import json
from types import SimpleNamespace

import httpx
import pytest
from openai import APIConnectionError, RateLimitError

from app.providers import AIProviderError
from app.providers.factory import UnknownProviderError, build_provider
from app.providers.ollama import OllamaProvider
from app.providers.openai import OpenAIProvider


class _FakeEventBase:
    """Marker type so tests can emulate SDK event classes cheaply."""

    def __init__(self, **kwargs) -> None:
        self.__dict__.update(kwargs)


class _FakeErrorEvent(_FakeEventBase):
    pass


class _FakeFailedEvent(_FakeEventBase):
    pass


def _event(ttype: str, delta: str | None = None, part: SimpleNamespace | None = None) -> SimpleNamespace:
    return SimpleNamespace(type=ttype, delta=delta, part=part)


def _part_delta(text: str) -> SimpleNamespace:
    return _event("response.output_text.delta", part=SimpleNamespace(text=text))


class FakeStreamManager:
    """SDK stream stand-in: async-iterable and async context manager."""

    def __init__(self, events):
        self.events = list(events)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    def __aiter__(self):
        return self._iterate()

    async def _iterate(self):
        for event in self.events:
            yield event


class FakeResponses:
    def __init__(self, events, exc=None):
        self._events = events
        self._exc = exc
        self.last_call: dict | None = None

    def stream(self, **kwargs):
        self.last_call = kwargs
        return FakeStreamManager(self._events)


class FakeClient:
    """Stand-in for ``AsyncOpenAI`` (never touches the network)."""

    def __init__(self, events=None, exc=None):
        self.responses = FakeResponses(events or [], exc)

    def __call__(self, **kwargs):
        return self


def _patch_client(monkeypatch, events, exc=None) -> FakeClient:
    client = FakeClient(events, exc)
    monkeypatch.setattr("app.providers.openai.AsyncOpenAI", client)
    return client


class TestOpenAIMessageMapping:
    def test_system_becomes_instructions(self) -> None:
        instructions, turns = OpenAIProvider.to_request_parts([
            {"role": "system", "content": "You are FALSO."},
            {"role": "user", "content": "hello"},
        ])
        assert instructions == "You are FALSO."
        assert turns == [{"role": "user", "content": "hello"}]

    def test_chat_history_roles_preserved(self) -> None:
        _, turns = OpenAIProvider.to_request_parts([
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "hey"},
            {"role": "user", "content": "again"},
        ])
        assert turns == [
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "hey"},
            {"role": "user", "content": "again"},
        ]

    def test_multiple_system_messages_joined(self) -> None:
        instructions, _ = OpenAIProvider.to_request_parts([
            {"role": "system", "content": "A"},
            {"role": "system", "content": "B"},
        ])
        assert instructions == "A\n\nB"

    def test_empty_input_gets_user_turn(self) -> None:
        instructions, turns = OpenAIProvider.to_request_parts([])
        assert instructions is None
        assert turns == [{"role": "user", "content": ""}]

    def test_blank_messages_skipped(self) -> None:
        _, turns = OpenAIProvider.to_request_parts([
            {"role": "system", "content": "   "},
            {"role": "user", "content": ""},
            {"role": "user", "content": "x"},
        ])
        assert turns == [{"role": "user", "content": "x"}]


class TestOpenAIDeltaParsing:
    def test_unified_delta_event(self) -> None:
        assert OpenAIProvider.extract_delta_text(_event("response.text.delta", "Hi ")) == "Hi "

    def test_legacy_output_text_delta(self) -> None:
        assert OpenAIProvider.extract_delta_text(_event("response.output_text.delta", "yo")) == "yo"

    def test_content_part_delta_falls_back_to_part_text(self) -> None:
        assert OpenAIProvider.extract_delta_text(_part_delta("part")) == "part"

    def test_non_text_events_ignored(self) -> None:
        assert OpenAIProvider.extract_delta_text(_event("response.reasoning_summary.text.delta", "hidden")) == ""
        assert OpenAIProvider.extract_delta_text(_event("response.completed")) == ""


class TestOpenAIStreaming:
    def _provider(self, key="secret-key") -> OpenAIProvider:
        return OpenAIProvider(model="gpt-5", api_key=key)

    async def test_streams_text_from_delta_events(self, monkeypatch) -> None:
        provider = self._provider()
        client = _patch_client(monkeypatch, [
            _event("response.created"),
            _event("response.text.delta", "Hello "),
            _event("response.text.delta", "world"),
            _event("response.completed"),
        ])

        chunks = [c.text async for c in provider.stream_chat(
            [{"role": "system", "content": "You are FALSO."}, {"role": "user", "content": "hi"}]
        )]
        assert chunks == ["Hello ", "world"]

        # The wire contract: instructions + input + streaming.
        call = client.responses.last_call
        assert call["model"] == "gpt-5"
        assert call["instructions"] == "You are FALSO."
        assert call["input"] == [{"role": "user", "content": "hi"}]
        assert call["stream_options"] == {"include_usage": True}

    async def test_missing_key_raises_before_client_creation(self, monkeypatch) -> None:
        provider = OpenAIProvider(model="gpt-5", api_key="")
        with pytest.raises(AIProviderError, match="OPENAI_API_KEY"):
            _ = [c async for c in provider.stream_chat([{"role": "user", "content": "x"}])]
        assert provider._client is None

    async def test_error_event_raises(self, monkeypatch) -> None:
        # Swap in lightweight stand-ins so the test does not depend on heavy
        # SDK pydantic models; the provider only does isinstance() checks.
        monkeypatch.setattr("app.providers.openai.ResponseErrorEvent", _FakeErrorEvent)
        monkeypatch.setattr("app.providers.openai.ResponseFailedEvent", _FakeFailedEvent)
        provider = self._provider()
        _patch_client(monkeypatch, [
            _FakeErrorEvent(message="queue full", code="rate_limited"),
        ])
        with pytest.raises(AIProviderError, match="queue full"):
            _ = [c async for c in provider.stream_chat([{"role": "user", "content": "x"}])]

    async def test_failed_event_raises(self, monkeypatch) -> None:
        monkeypatch.setattr("app.providers.openai.ResponseErrorEvent", _FakeErrorEvent)
        monkeypatch.setattr("app.providers.openai.ResponseFailedEvent", _FakeFailedEvent)
        provider = self._provider()
        _patch_client(monkeypatch, [_FakeFailedEvent(type="failed")])
        with pytest.raises(AIProviderError, match="failed"):
            _ = [c async for c in provider.stream_chat([{"role": "user", "content": "x"}])]


class TestOpenAIErrorMapping:
    def setup_method(self) -> None:
        self.provider = OpenAIProvider(model="gpt-5", api_key="k")

    def _req(self) -> httpx.Request:
        return httpx.Request("POST", "https://api.openai.com/v1/responses")

    def test_connection_error(self) -> None:
        exc = APIConnectionError(request=self._req())
        assert "connection failed" in self.provider._map_error(exc)

    def test_rate_limit_status(self) -> None:
        exc = RateLimitError("rate", response=httpx.Response(429, request=self._req()), body=None)
        assert self.provider._map_error(exc) == "OpenAI API error 429 (rate limit or quota exceeded)"

    def test_503_queue_full_hint(self) -> None:
        exc = RateLimitError("busy", response=httpx.Response(503, request=self._req()), body=None)
        assert "service unavailable (request queue full)" in self.provider._map_error(exc)

    def test_model_not_found_hint(self) -> None:
        exc = RateLimitError("nf", response=httpx.Response(404, request=self._req()), body=None)
        assert "model not found" in self.provider._map_error(exc)


class FakeHttpStream:
    """HTTPX-style stream stand-in for the Ollama provider (NDJSON)."""

    def __init__(self, lines, status: int = 200, body: bytes = b"", exc=None):
        self.lines = list(lines)
        self.status_code = status
        self.body = body
        self.exc = exc

    async def __aenter__(self):
        if self.exc is not None:
            raise self.exc
        return self

    async def __aexit__(self, *exc):
        return None

    async def aread(self) -> bytes:
        return self.body

    async def aiter_lines(self):
        for line in self.lines:
            yield line


class FakeHttpClient:
    def __init__(self, stream: FakeHttpStream):
        self._stream = stream
        self.last_request: dict | None = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return None

    def stream(self, method: str, url: str, **kwargs) -> FakeHttpStream:
        self.last_request = {"method": method, "url": url, **kwargs}
        return self._stream


class TestOllamaStreaming:
    def _provider(self) -> OllamaProvider:
        return OllamaProvider(model="qwen2.5:3b")

    def _patch_http(self, monkeypatch, stream: FakeHttpStream) -> FakeHttpClient:
        client = FakeHttpClient(stream)
        monkeypatch.setattr("app.providers.ollama.httpx.AsyncClient", lambda **kw: client)
        return client

    async def test_streams_ndjson_chunks(self, monkeypatch) -> None:
        provider = self._provider()
        stream = FakeHttpStream([
            json.dumps({"model": "qwen2.5:3b", "message": {"content": "Hi "}, "done": False}),
            json.dumps({"model": "qwen2.5:3b", "message": {"content": "there"}, "done": True}),
        ])
        client = self._patch_http(monkeypatch, stream)

        chunks = [(c.text, c.done) async for c in provider.stream_chat([{"role": "user", "content": "hi"}])]
        assert chunks == [("Hi ", False), ("there", True)]

        request = client.last_request
        assert request["json"]["model"] == "qwen2.5:3b"
        assert request["json"]["stream"] is True

    async def test_malformed_line_skipped_stream_survives(self, monkeypatch) -> None:
        provider = self._provider()
        self._patch_http(monkeypatch, FakeHttpStream([
            json.dumps({"message": {"content": "Hi "}, "done": False}),
            "NOT JSON {{{",
            "not-an-object",
            json.dumps({"message": {"content": "there"}, "done": True}),
        ]))

        chunks = [c.text async for c in provider.stream_chat([{"role": "user", "content": "hi"}])]
        assert chunks == ["Hi ", "there"]


class _FakeSettings:
    def __init__(self, **kwargs) -> None:
        defaults = {
            "ai_provider": "openai",
            "openai_model": "OAI-M",
            "openai_api_key": "KEY",
            "openai_base_url": "",
            "ollama_model": "OLLAMA-M",
            "ollama_base_url": "http://localhost:11434",
        }
        defaults.update(kwargs)
        for key, value in defaults.items():
            setattr(self, key, value)


class TestProviderFactory:
    def test_builds_openai_by_default(self) -> None:
        provider = build_provider(_FakeSettings())
        assert isinstance(provider, OpenAIProvider)
        assert provider.model == "OAI-M"

    def test_builds_openai_explicit(self) -> None:
        provider = build_provider(_FakeSettings(ai_provider="openai", openai_model="gpt-5"))
        assert provider.model == "gpt-5"

    def test_builds_ollama(self) -> None:
        provider = build_provider(_FakeSettings(ai_provider="ollama"))
        assert isinstance(provider, OllamaProvider)
        assert provider.model == "OLLAMA-M"

    def test_provider_name_is_case_insensitive(self) -> None:
        provider = build_provider(_FakeSettings(ai_provider="  OpenAI  "))
        assert provider.name == "openai"

    def test_unknown_provider_raises(self) -> None:
        with pytest.raises(UnknownProviderError) as exc:
            build_provider(_FakeSettings(ai_provider="claude"))
        assert "claude" in str(exc.value)
        assert "openai" in str(exc.value)  # tells the user what IS available