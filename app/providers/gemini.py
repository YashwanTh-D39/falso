"""Gemini AI provider — streaming chat via Google AI Studio API / Gemini API.

selecting this provider makes Gemini (Google AI Studio) the primary AI engine for Falso.
The API key is read server-side only via GEMINI_API_KEY in .env.

Resilience:
- Streaming JSON chunks parsed from Google AI Studio streamGenerateContent SSE endpoint;
- Zero mandatory external SDK dependency (uses lightweight httpx.AsyncClient);
- User-safe AIProviderError reporting without exposing API keys.
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.providers.base import AIProviderError, BaseAIProvider, ProviderChunk
from config.settings import settings

logger = logging.getLogger(__name__)

DEFAULT_GEMINI_MODEL = "gemini-3.6-flash"
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"


class GeminiProvider(BaseAIProvider):
    """Streams chat completions from the Gemini API (Google AI Studio)."""

    name = "gemini"

    def __init__(
        self,
        model: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> None:
        self.model = model or getattr(settings, "gemini_model", DEFAULT_GEMINI_MODEL)
        self.api_key = api_key if api_key is not None else getattr(settings, "gemini_api_key", "")
        self.base_url = (base_url or "").strip().rstrip("/") or GEMINI_BASE_URL
        self._client: httpx.AsyncClient | None = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            timeout = httpx.Timeout(
                settings.ai_timeout_seconds, connect=5.0, read=30.0
            )
            self._client = httpx.AsyncClient(timeout=timeout)
        return self._client

    async def aclose(self) -> None:
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    @staticmethod
    def to_gemini_payload(messages: list[dict]) -> dict[str, Any]:
        """Convert neutral message list into Gemini streamGenerateContent payload shape.

        system turns -> top-level systemInstruction
        user/assistant turns -> contents list with 'user'/'model' roles
        """
        system_instruction = None
        contents: list[dict[str, Any]] = []

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if not content:
                continue

            if role == "system":
                system_instruction = {"parts": [{"text": content}]}
            else:
                gemini_role = "model" if role in ("assistant", "model") else "user"
                contents.append({"role": gemini_role, "parts": [{"text": content}]})

        payload: dict[str, Any] = {"contents": contents}
        if system_instruction:
            payload["systemInstruction"] = system_instruction
        return payload

    async def stream_chat(
        self, messages: list[dict]
    ) -> AsyncIterator[ProviderChunk]:
        if not self.api_key:
            raise AIProviderError(
                "Gemini API key not configured. Please add GEMINI_API_KEY to your .env file."
            )

        payload = self.to_gemini_payload(messages)
        endpoint = f"{self.base_url}/models/{self.model}:streamGenerateContent?alt=sse&key={self.api_key}"

        client = self._get_client()
        try:
            async with client.stream(
                "POST",
                endpoint,
                json=payload,
                headers={"Content-Type": "application/json"},
            ) as response:
                if response.status_code == 404 and self.model != DEFAULT_GEMINI_MODEL:
                    logger.warning(
                        "Configured Gemini model %r is unavailable — automatically falling back to %r",
                        self.model,
                        DEFAULT_GEMINI_MODEL,
                    )
                    self.model = DEFAULT_GEMINI_MODEL
                    fallback_endpoint = f"{self.base_url}/models/{self.model}:streamGenerateContent?alt=sse&key={self.api_key}"
                    async with client.stream(
                        "POST",
                        fallback_endpoint,
                        json=payload,
                        headers={"Content-Type": "application/json"},
                    ) as fb_response:
                        if fb_response.status_code != 200:
                            fb_body = await fb_response.aread()
                            raise AIProviderError(f"Gemini API fallback error {fb_response.status_code}: {fb_body.decode('utf-8', errors='ignore')}")
                        async for line in fb_response.aiter_lines():
                            line = line.strip()
                            if not line.startswith("data:"):
                                continue
                            raw_data = line[5:].strip()
                            if not raw_data or raw_data == "[DONE]":
                                continue
                            try:
                                chunk_json = json.loads(raw_data)
                                candidates = chunk_json.get("candidates", [])
                                if not candidates:
                                    continue
                                parts = candidates[0].get("content", {}).get("parts", [])
                                for part in parts:
                                    text_delta = part.get("text", "")
                                    if text_delta:
                                        yield ProviderChunk(text=text_delta)
                            except json.JSONDecodeError:
                                continue
                    return

                if response.status_code != 200:
                    body = await response.aread()
                    error_msg = f"Gemini API error {response.status_code}"
                    try:
                        err_json = json.loads(body.decode("utf-8"))
                        if "error" in err_json:
                            error_msg += f": {err_json['error'].get('message', '')}"
                    except Exception as exc:  # noqa: BLE001
                        logger.debug("Could not parse Gemini error JSON: %s", exc)
                    raise AIProviderError(error_msg)

                async for line in response.aiter_lines():
                    line = line.strip()
                    if not line.startswith("data:"):
                        continue

                    raw_data = line[5:].strip()
                    if not raw_data or raw_data == "[DONE]":
                        continue

                    try:
                        chunk_json = json.loads(raw_data)
                        candidates = chunk_json.get("candidates", [])
                        if not candidates:
                            continue

                        parts = candidates[0].get("content", {}).get("parts", [])
                        for part in parts:
                            text_delta = part.get("text", "")
                            if text_delta:
                                yield ProviderChunk(text=text_delta)
                    except json.JSONDecodeError:
                        continue
        except httpx.RequestError as exc:
            raise AIProviderError(f"Gemini API network error: {exc}") from exc
