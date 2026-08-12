"""Unit tests for NVIDIA Nemotron Provider and Fallback mechanism."""

import json
import pytest
import httpx

from app.providers.base import AIProviderError
from app.providers.factory import build_provider
from app.providers.nvidia import NVIDIAProvider
from app.services.brain import BrainService
from config.settings import Settings


class FakeStream:
    def __init__(self, lines: list[str], status_code: int = 200, body: bytes = b""):
        self.lines = lines
        self.status_code = status_code
        self.body = body

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    async def aread(self) -> bytes:
        return self.body

    async def aiter_lines(self):
        for line in self.lines:
            yield line


class FakeClient:
    def __init__(self, stream_resp: FakeStream, get_resp: FakeStream | None = None):
        self._stream_resp = stream_resp
        self._get_resp = get_resp
        self.last_request: dict | None = None
        self.is_closed = False


    def stream(self, method: str, url: str, **kwargs):
        self.last_request = {"method": method, "url": url, **kwargs}
        return self._stream_resp

    async def get(self, url: str, **kwargs):
        return self._get_resp


class TestNVIDIAProvider:
    def test_provider_initialization(self):
        provider = NVIDIAProvider(
            model="nvidia/llama-3.1-nemotron-70b-instruct",
            api_key="test-key",
        )
        assert provider.name == "nvidia"
        assert provider.model == "nvidia/llama-3.1-nemotron-70b-instruct"
        assert provider.api_key == "test-key"

    @pytest.mark.asyncio
    async def test_missing_api_key_raises(self):
        provider = NVIDIAProvider(api_key="")
        with pytest.raises(AIProviderError, match="NVIDIA API key not configured"):
            _ = [c async for c in provider.stream_chat([{"role": "user", "content": "hi"}])]

    @pytest.mark.asyncio
    async def test_successful_streaming(self, monkeypatch):
        provider = NVIDIAProvider(
            model="nvidia/llama-3.1-nemotron-70b-instruct",
            api_key="valid-key",
        )

        stream = FakeStream([
            "data: " + json.dumps({"choices": [{"delta": {"content": "Hello"}, "finish_reason": None}]}),
            "data: " + json.dumps({"choices": [{"delta": {"content": " world!"}, "finish_reason": "stop"}]}),
            "data: [DONE]",
        ])
        fake_client = FakeClient(stream)
        monkeypatch.setattr(provider, "_client", fake_client)

        chunks = [c.text async for c in provider.stream_chat([{"role": "user", "content": "hi"}])]
        assert chunks == ["Hello", " world!"]
        assert fake_client.last_request["headers"]["Authorization"] == "Bearer valid-key"
        assert fake_client.last_request["json"]["model"] == "nvidia/llama-3.1-nemotron-70b-instruct"

    @pytest.mark.asyncio
    async def test_401_error_handling(self, monkeypatch):
        provider = NVIDIAProvider(api_key="bad-key")
        stream = FakeStream([], status_code=401, body=b'{"detail":"Authentication failed"}')
        monkeypatch.setattr(provider, "_client", FakeClient(stream))

        with pytest.raises(AIProviderError, match="401"):
            _ = [c async for c in provider.stream_chat([{"role": "user", "content": "hi"}])]

    @pytest.mark.asyncio
    async def test_factory_builds_nvidia(self):
        s = Settings(
            llm_provider="nvidia",
            nvidia_inference_api_key="test-key",
            nvidia_model="nvidia/llama-3.1-nemotron-70b-instruct",
        )
        provider = build_provider(s)
        assert isinstance(provider, NVIDIAProvider)
        assert provider.model == "nvidia/llama-3.1-nemotron-70b-instruct"


class TestFallbackMechanism:
    @pytest.mark.asyncio
    async def test_brain_service_falls_back_to_ollama_on_nvidia_failure(self, monkeypatch):
        # Configure NVIDIA as primary and Ollama as fallback
        failing_nvidia = NVIDIAProvider(api_key="")
        brain = BrainService(provider=failing_nvidia)

        # Mock Ollama provider to succeed
        class FakeOllama:
            name = "ollama"
            model = "gemma3:4b"

            async def stream_chat(self, messages):
                yield type("Chunk", (), {"text": "Fallback response from Ollama", "done": True})()

        monkeypatch.setattr("app.services.brain.build_provider", lambda s, provider_name=None: FakeOllama())

        chunks = []
        async for line in brain.chat("what is 2+2?"):
            parsed = json.loads(line)
            if "response" in parsed and parsed["response"]:
                chunks.append(parsed["response"])

        assert "Fallback response from Ollama" in chunks
