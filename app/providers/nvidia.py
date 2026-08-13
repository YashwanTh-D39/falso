"""NVIDIA provider — streaming chat completions via NVIDIA Nemotron API.

The NVIDIA hosted endpoint is OpenAI-compatible:
  POST https://integrate.api.nvidia.com/v1/chat/completions (stream=true)

Credentials are read server-side only from NVIDIA_INFERENCE_API_KEY in .env.
API keys are never logged, placed in URLs, or sent to the client/browser.
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import AsyncIterator

import httpx

from app.providers.base import AIProviderError, BaseAIProvider, ProviderChunk

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://integrate.api.nvidia.com/v1"
DEFAULT_MODEL = "nvidia/llama-3.3-nemotron-super-49b-v1"

_STATUS_HINTS = {
    401: "authentication failed — check NVIDIA_INFERENCE_API_KEY in .env",
    403: "access denied — key lacks permission for this model",
    404: "model not found — check NVIDIA_MODEL in .env",
    429: "rate limit exceeded",
    500: "NVIDIA server error",
    502: "NVIDIA gateway error",
    503: "NVIDIA service unavailable",
    504: "NVIDIA gateway timeout",
}


class NVIDIAProvider(BaseAIProvider):
    """Streams chat completions from the OpenAI-compatible NVIDIA API."""

    name = "nvidia"

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        api_key: str = "",
        base_url: str = DEFAULT_BASE_URL,
    ) -> None:
        self.model = (model or DEFAULT_MODEL).strip()
        self.api_key = (api_key or "").strip()
        self.base_url = (base_url or DEFAULT_BASE_URL).rstrip("/")
        self._client: httpx.AsyncClient | None = None
        self.last_nvidia_first_token_ms: float = 0.0
        logger.info("NVIDIA provider selected")
        logger.info("NVIDIA model selected: %s", self.model)

    @property
    def client(self) -> httpx.AsyncClient:
        """Lazily created persistent client for connection reuse across chats."""
        if self._client is None or self._client.is_closed:
            timeout = httpx.Timeout(60.0, connect=15.0, read=60.0)
            limits = httpx.Limits(
                max_keepalive_connections=20,
                max_connections=50,
                keepalive_expiry=300.0,
            )
            self._client = httpx.AsyncClient(timeout=timeout, limits=limits)
        return self._client

    async def aclose(self) -> None:
        """Explicitly close the HTTP client."""
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def verify_model_availability(self) -> bool:
        """Check if the configured model exists in NVIDIA's /models catalog and warm connection pool."""
        if not self.api_key:
            logger.debug("NVIDIA API key not set — skipping network model verification.")
            return False
        try:
            headers = {"Authorization": f"Bearer {self.api_key}"}
            client = self.client
            resp = await client.get(f"{self.base_url}/models", headers=headers)
            try:
                if resp.status_code == 200:
                    data = resp.json()
                    model_ids = [m.get("id") for m in data.get("data", []) if isinstance(m, dict)]
                    if self.model in model_ids:
                        logger.info("NVIDIA model verified & connection warmed: %s", self.model)
                        return True
                    else:
                        logger.warning(
                            "Configured NVIDIA model %r not found in catalog (%d models listed). "
                            "NVIDIA API may reject completions.",
                            self.model,
                            len(model_ids),
                        )
                        return False
            finally:
                await resp.aclose()
        except Exception as exc:
            logger.debug("NVIDIA model verification failed: %s", exc)
        return False

    async def stream_chat(self, messages: list[dict], max_tokens: int | None = None) -> AsyncIterator[ProviderChunk]:
        if not self.api_key:
            raise AIProviderError(
                "NVIDIA API key not configured — set NVIDIA_INFERENCE_API_KEY in .env"
            )

        client = self.client
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            "temperature": 0.6,
            "top_p": 0.7,
            "max_tokens": max_tokens or 2048,
        }

        t_nvidia_req_start = time.perf_counter()
        cold_start_logged = False
        logger.info("[LATENCY] NVIDIA_REQUEST_START | model=%s", self.model)

        try:
            async with client.stream(
                "POST",
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
            ) as resp:
                logger.info("[LATENCY] NVIDIA_HEADERS_RECEIVED | status=%d", resp.status_code)
                if resp.status_code != 200:
                    body = (await resp.aread())[:500].decode(errors="replace")
                    hint = _STATUS_HINTS.get(resp.status_code, f"API error {resp.status_code}")
                    err_detail = f"NVIDIA API error {resp.status_code} ({hint}): {body}"
                    logger.error("NVIDIA API stream failed: status=%d hint=%r", resp.status_code, hint)
                    raise AIProviderError(err_detail)

                first_token_received = False
                chunk_index = 0
                async for line in resp.aiter_lines():
                    # Cold-start detection: check elapsed before parsing
                    if not first_token_received and not cold_start_logged:
                        waiting_ms = (time.perf_counter() - t_nvidia_req_start) * 1000.0
                        if waiting_ms > 3000.0:
                            cold_start_logged = True
                            logger.warning(
                                "[NVIDIA] COLD_START_DETECTED | waiting=%.0fms | "
                                "model=%s | No tokens received yet",
                                waiting_ms, self.model,
                            )

                    trimmed = line.strip()
                    if not trimmed:
                        continue
                    if trimmed.startswith("data:"):
                        data_str = trimmed[5:].strip()
                        if data_str == "[DONE]":
                            break
                        try:
                            parsed = json.loads(data_str)
                            choices = parsed.get("choices") or []
                            if choices and isinstance(choices, list):
                                delta = choices[0].get("delta") or {}
                                content = delta.get("content") or ""
                                finish_reason = choices[0].get("finish_reason")
                                if content:
                                    chunk_index += 1
                                    elapsed = (time.perf_counter() - t_nvidia_req_start) * 1000.0
                                    safe_preview = repr(content[:10])
                                    logger.info(
                                        "[NVIDIA_STREAM] chunk=%d elapsed=%.2fms len=%d preview=%s",
                                        chunk_index,
                                        elapsed,
                                        len(content),
                                        safe_preview,
                                    )
                                    if not first_token_received:
                                        first_token_received = True
                                        self.last_nvidia_first_token_ms = elapsed
                                        logger.info(
                                            "[LATENCY] NVIDIA_FIRST_TOKEN | latency=%.2fms",
                                            self.last_nvidia_first_token_ms,
                                        )
                                        if cold_start_logged:
                                            logger.info(
                                                "[NVIDIA] COLD_START_COMPLETE | total=%.0fms",
                                                elapsed,
                                            )
                                    yield ProviderChunk(
                                        text=content,
                                        done=bool(finish_reason),
                                    )
                        except (json.JSONDecodeError, AttributeError, KeyError) as parse_err:
                            logger.debug("Skipping malformed SSE chunk: %r (%s)", trimmed[:100], parse_err)
                            continue

        except httpx.TimeoutException as exc:
            logger.error("NVIDIA API request timed out: %s", exc)
            raise AIProviderError("NVIDIA API request timed out") from exc
        except httpx.RequestError as exc:
            logger.error("NVIDIA API connection failed: %s", exc)
            raise AIProviderError(f"NVIDIA connection failed: {exc}") from exc
