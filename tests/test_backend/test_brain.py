import json

import pytest

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


class FakeLineStream:
    def __init__(self, lines: list | None = None, status: int = 200, body: bytes = b"", exc=None):
        self.lines = lines or []
        self.status_code = status
        self.body = body
        self.exc = exc

    async def __aenter__(self):
        if self.exc is not None:
            raise self.exc
        return self

    async def __aexit__(self, *exc) -> None:
        return None

    async def aread(self) -> bytes:
        return self.body

    async def aiter_lines(self):
        for line in self.lines:
            yield json.dumps(line)


class FakeClient:
    def __init__(self, stream: FakeLineStream):
        self._stream = stream

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc) -> None:
        return None

    def stream(self, method: str, url: str, **kwargs) -> FakeLineStream:
        return self._stream


class TestBrainServiceLlmStreaming:
    """LLM streaming path with a mocked Ollama client."""

    def setup_method(self) -> None:
        self.service = BrainService()

    def _patch_ollama(self, monkeypatch, stream: FakeLineStream) -> None:
        monkeypatch.setattr(
            "app.services.brain.httpx.AsyncClient",
            lambda **kwargs: FakeClient(stream),
        )
    async def test_streams_assistant_chunks(self, monkeypatch) -> None:
        stream = FakeLineStream([
            {"model": "qwen2.5:3b", "message": {"content": "Hi "}, "done": False},
            {"model": "qwen2.5:3b", "message": {"content": "there"}, "done": True},
        ])
        self._patch_ollama(monkeypatch, stream)

        events = [
            json.loads(line)
            async for line in self.service.chat("hello, no tool words here")
        ]
        assert "".join(e.get("response", "") for e in events) == "Hi there"
        assert events[-1]["done"] is True
        assert events[0]["model"] == "qwen2.5:3b"

    async def test_surfaces_ollama_http_error(self, monkeypatch) -> None:
        stream = FakeLineStream([], status=500, body=b"ollama is down")
        self._patch_ollama(monkeypatch, stream)

        events = [
            json.loads(line)
            async for line in self.service.chat("hello, no tool words here")
        ]
        assert len(events) == 1
        assert "Ollama error" in events[0]["error"]

    async def test_malformed_line_skipped_stream_survives(self, monkeypatch) -> None:
        stream = FakeLineStream([
            {"model": "qwen2.5:3b", "message": {"content": "Hi "}, "done": False},
            "NOT JSON {{{",
            {"model": "qwen2.5:3b", "message": {"content": "there"}, "done": True},
        ])
        self._patch_ollama(monkeypatch, stream)

        events = [
            json.loads(line)
            async for line in self.service.chat("hello, no tool words here")
        ]
        assert "".join(e.get("response", "") for e in events) == "Hi there"
        assert events[-1]["done"] is True

    async def test_connect_error_yields_error_line(self, monkeypatch) -> None:
        import httpx

        stream = FakeLineStream(exc=httpx.ConnectError("connection refused"))
        self._patch_ollama(monkeypatch, stream)

        events = [
            json.loads(line)
            async for line in self.service.chat("hello, no tool words here")
        ]
        assert len(events) == 1
        assert "Ollama connection failed" in events[0]["error"]

    async def test_read_timeout_yields_error_line(self, monkeypatch) -> None:
        import httpx

        stream = FakeLineStream(exc=httpx.ReadTimeout("slow ollama"))
        self._patch_ollama(monkeypatch, stream)

        events = [
            json.loads(line)
            async for line in self.service.chat("hello, no tool words here")
        ]
        assert len(events) == 1
        assert "Ollama connection failed" in events[0]["error"]


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
