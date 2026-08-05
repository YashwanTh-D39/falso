"""OpenAI provider — streaming chat via the official SDK (Responses API).

Uses ``client.responses.stream(...)`` (the current Responses API, not the
deprecated Chat Completions path): the system prompt is sent as the top-level
``instructions`` argument and conversation turns become ``input`` messages. The
API key is read server-side only and is never placed in a URL, logged, or
shipped to the browser.

Resilience:
- the SDK retries transient 408/429/5xx responses (including 503) with
  exponential backoff + jitter before we ever see the error;
- a per-provider ``asyncio.Lock`` guarantees a single in-flight stream;
- the stream is used via ``async with`` so the HTTP response and the lock are
  both released when the generator ends — including on client disconnect.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator

from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AsyncOpenAI,
    OpenAIError,
)
from openai.types.responses import ResponseErrorEvent, ResponseFailedEvent

from app.providers.base import AIProviderError, BaseAIProvider, ProviderChunk

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "gpt-5"

#: Per-request timeout (seconds). The SDK keeps the connection alive while
#: tokens are streaming, so this is a floors, not a cap, on generation.
REQUEST_TIMEOUT = 60.0

#: SDK-level retry count for transient network/HTTP failures. On each attempt
#: the SDK waits exponentially longer (with jitter) — our backoff.
CONNECT_RETRIES = 5

#: Stream event ``type`` suffixes that carry assistant text. SDK-version
#: aware: the unified 2.x SDK ships "response.text.delta"; some 1.x releases
#: used "response.output_text.delta".
_TEXT_DELTA_TYPES = ("response.text.delta", "response.output_text.delta")

#: HTTP status -> short user-facing hint (used after SDK retries are spent).
_STATUS_HINTS = {
    400: "bad request",
    401: "authentication failed — check OPENAI_API_KEY",
    403: "access denied — key lacks permission for this model",
    404: "model not found — check OPENAI_MODEL",
    429: "rate limit or quota exceeded",
    500: "OpenAI server error",
    503: "service unavailable (request queue full)",
}


class OpenAIProvider(BaseAIProvider):
    """Streams chat completions from the OpenAI Responses API."""

    name = "openai"

    def __init__(self, model: str, api_key: str, base_url: str | None = None) -> None:
        self.model = model or DEFAULT_MODEL
        self.api_key = api_key or ""
        self.base_url = (base_url or "").strip() or None
        self._client: AsyncOpenAI | None = None
        # A single in-flight stream per provider instance (module docstring).
        self._lock = asyncio.Lock()

    # ── Client lifecycle ─────────────────────────────────────────────────

    def _get_client(self) -> AsyncOpenAI:
        """Build the SDK client lazily (must not exist when the key is empty)."""
        if self._client is None:
            kwargs = {
                "api_key": self.api_key,
                "max_retries": CONNECT_RETRIES,
                "timeout": REQUEST_TIMEOUT,
            }
            if self.base_url:
                kwargs["base_url"] = self.base_url
            self._client = AsyncOpenAI(**kwargs)
        return self._client

    # ── Neutral messages -> Responses API request ────────────────────────

    @staticmethod
    def to_request_parts(messages: list[dict]) -> tuple[str | None, list[dict]]:
        """Split the neutral message list into ``(instructions, input)``.

        ``system`` turns become the Responses API top-level ``instructions``;
        ``user``/``assistant`` turns become ``input`` messages, so forwarding
        previous conversation turns (chat history) works out of the box.
        """
        instructions: list[str] = []
        input_turns: list[dict] = []
        for msg in messages:
            role = msg.get("role", "user")
            content = (msg.get("content") or "").strip()
            if role == "system":
                if content:
                    instructions.append(content)
                continue
            if content:
                input_turns.append({"role": role or "user", "content": content})
        if not input_turns:
            input_turns.append({"role": "user", "content": ""})
        return ("\n\n".join(instructions) or None), input_turns

    # ── Stream event parsing (SDK-version tolerant) ──────────────────────

    @staticmethod
    def extract_delta_text(event) -> str:
        """Return the incremental assistant text carried by one stream event."""
        etype = getattr(event, "type", "")
        if not any(t in etype for t in _TEXT_DELTA_TYPES):
            return ""
        text = getattr(event, "delta", None) or None
        if not text:
            part = getattr(event, "part", None)
            text = (getattr(part, "text", "") or "") if part is not None else ""
        return text or ""

    # ── Error mapping (user-safe, no credentials) ────────────────────────

    def _map_error(self, exc: OpenAIError) -> str:
        if isinstance(exc, APITimeoutError):
            return "OpenAI request timed out"
        if isinstance(exc, APIConnectionError):
            return "OpenAI connection failed — check the network and OPENAI_API_KEY"
        if isinstance(exc, APIStatusError):
            hint = _STATUS_HINTS.get(exc.status_code, "API error")
            return f"OpenAI API error {exc.status_code} ({hint})"
        base = str(exc).strip()
        return f"OpenAI API error: {base}" if base else "OpenAI API error"

    # ── Public contract ──────────────────────────────────────────────────

    async def stream_chat(self, messages: list[dict]) -> AsyncIterator[ProviderChunk]:
        if not self.api_key:
            raise AIProviderError(
                "OpenAI API key not configured — set OPENAI_API_KEY in .env"
            )

        instructions, input_turns = self.to_request_parts(messages)
        client = self._get_client()

        # Single-flight: another chat turn can keep its stream running, but a
        # second request simply waits here rather than piling up a queue at
        # the vendor. Best-effort the 503/queue-full class of problems.
        async with self._lock:
            try:
                async with client.responses.stream(
                    model=self.model,
                    input=input_turns,
                    instructions=instructions,
                    stream_options={"include_usage": True},
                ) as stream:
                    async for event in stream:
                        if isinstance(event, ResponseErrorEvent):
                            raise AIProviderError(
                                "OpenAI API error: " + (event.message or "unknown")
                            )
                        if isinstance(event, ResponseFailedEvent):
                            raise AIProviderError("OpenAI API request failed")
                        text = self.extract_delta_text(event)
                        if text:
                            yield ProviderChunk(text=text)
            except OpenAIError as exc:
                # Applies only after the SDK retries (backoff) gave up, so the
                # message doubles as the "service is busy right now" notice.
                raise AIProviderError(self._map_error(exc)) from exc