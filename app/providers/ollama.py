"""Ollama provider — the original local backend, preserved as a provider.

Ollama's ``/api/chat`` already accepts OpenAI-style messages, so the native
wire format and the provider contract coincide. Malformed lines from the
upstream stream (proxy corruption, mid-line flushes) are skipped rather than
aborting the whole stream — the same resilience the old inline client had.
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator

import httpx

from app.providers.base import AIProviderError, BaseAIProvider, ProviderChunk

logger = logging.getLogger(__name__)

#: Connect in 5 s, read between bytes up to 30 s, 300 s total (large prompts).
TIMEOUT = httpx.Timeout(300.0, connect=5.0, read=30.0)

DEFAULT_BASE_URL = "http://localhost:11434"


class OllamaProvider(BaseAIProvider):
    """Streams chat completions from the local Ollama ``/api/chat`` endpoint.

    Selecting this provider keeps Falso fully offline: set ``AI_PROVIDER=ollama``
    in ``.env`` (plus ``OLLAMA_BASE_URL``/``OLLAMA_MODEL`` if non-default).
    """

    name = "ollama"

    def __init__(
        self,
        model: str,
        base_url: str = DEFAULT_BASE_URL,
    ) -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")
        self._client: httpx.AsyncClient | None = None

    @property
    def client(self) -> httpx.AsyncClient:
        """Lazily-created persistent client: TCP connection reuse across chats."""
        if self._client is None or self._client.is_closed:
            from config.settings import settings
            timeout = httpx.Timeout(settings.ai_timeout_seconds, connect=5.0, read=30.0)
            self._client = httpx.AsyncClient(timeout=timeout)
        return self._client

    async def aclose(self) -> None:
        """Explicitly close the underlying HTTP client."""
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def stream_chat(self, messages: list[dict]) -> AsyncIterator[ProviderChunk]:
        client = self.client
        try:
            async with client.stream(
                "POST",
                f"{self.base_url}/api/chat",
                json={
                    "model": self.model,
                    "messages": messages,
                    "stream": True,
                    "keep_alive": "24h",
                    "options": {
                        "num_ctx": 2048,
                        "temperature": 0.7,
                    },
                },
            ) as resp:
                if resp.status_code != 200:
                    body = (await resp.aread())[:500].decode(errors="replace")
                    raise AIProviderError(f"Ollama error {resp.status_code}: {body}")

                async for line in resp.aiter_lines():
                    if not line.strip():
                        continue
                    try:
                        data = json.loads(line)
                    except (json.JSONDecodeError, ValueError):
                        logger.debug("Skipping malformed Ollama line: %r", line[:200])
                        continue
                    if not isinstance(data, dict):
                        logger.debug("Skipping non-object Ollama line: %r", line[:200])
                        continue
                    chunk = (data.get("message") or {}).get("content", "") or ""
                    if chunk:
                        yield ProviderChunk(text=chunk, done=bool(data.get("done")))
        except httpx.RequestError as exc:
            raise AIProviderError(f"Ollama connection failed: {exc}") from exc

    async def warm(self) -> bool:
        """Cheap keep-alive ping: loads/pins the model without generating."""
        try:
            async with self.client.stream(
                "POST",
                f"{self.base_url}/api/generate",
                json={"model": self.model, "prompt": "", "keep_alive": "24h"},
            ) as resp:
                if resp.status_code != 200:
                    return False
                async for _line in resp.aiter_lines():
                    pass
                return True
        except httpx.RequestError as exc:
            logger.debug("Ollama warmup failed: %s", exc)
            return False