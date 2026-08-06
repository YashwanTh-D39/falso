from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from typing import Any

import httpx

from config.settings import settings
from voice.base import BaseTTSEngine, TTSResult
from voice.tts import LocalTTSEngine

logger = logging.getLogger(__name__)

DEFAULT_ELEVENLABS_VOICE = "EXAVITQu4vr4xnSDxMaL"  # Bella / Sarah: Warm, natural, medium pitch
DEFAULT_ELEVENLABS_MODEL = "eleven_monolingual_v1"
ELEVENLABS_BASE_URL = "https://api.elevenlabs.io/v1/text-to-speech"


class ElevenLabsTTSEngine(BaseTTSEngine):
    """Cloud Text-to-Speech engine using ElevenLabs API with automatic fallback.

    Streams MP3 audio directly from ElevenLabs. If the API key is unconfigured
    or an API/network error occurs, synthesis falls back seamlessly to the native
    LocalTTSEngine without throwing exceptions to callers.
    """

    name = "elevenlabs"

    def __init__(
        self,
        api_key: str | None = None,
        voice_id: str | None = None,
        model_id: str | None = None,
        fallback_engine: BaseTTSEngine | None = None,
    ) -> None:
        self.api_key = api_key if api_key is not None else settings.elevenlabs_api_key
        self.voice_id = (
            voice_id or settings.elevenlabs_voice_id or DEFAULT_ELEVENLABS_VOICE
        )
        self.model_id = (
            model_id or settings.elevenlabs_model_id or DEFAULT_ELEVENLABS_MODEL
        )
        self.fallback_engine = fallback_engine or LocalTTSEngine()
        self._client: httpx.AsyncClient | None = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(30.0, connect=5.0),
                headers={
                    "Accept": "audio/mpeg",
                    "Content-Type": "application/json",
                    "xi-api-key": self.api_key,
                },
            )
        return self._client

    async def aclose(self) -> None:
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def synthesize(self, text: str, **kwargs: Any) -> TTSResult:
        from voice.cleaner import clean_text_for_speech
        clean_text = clean_text_for_speech(text)
        if not clean_text:
            return TTSResult(audio_data=b"", format="mp3", duration_seconds=0.0)

        if not self.api_key:
            logger.info("[TTS]\nProvider: Local TTS (Fallback)\nVoice: Windows SAPI5\nLatency: 0ms")
            return await self.fallback_engine.synthesize(clean_text, **kwargs)

        url = f"{ELEVENLABS_BASE_URL}/{self.voice_id}"
        payload = {
            "text": clean_text,
            "model_id": self.model_id,
            "voice_settings": {
                "stability": 0.70,
                "similarity_boost": 0.75,
                "style": 0.20,
                "use_speaker_boost": True
            },
        }

        start_t = time.perf_counter()
        try:
            client = self._get_client()
            resp = await client.post(url, json=payload)
            latency_ms = round((time.perf_counter() - start_t) * 1000, 1)

            if resp.status_code != 200:
                logger.warning(
                    "[TTS]\nProvider: Local TTS (Fallback)\nVoice: Windows SAPI5\nLatency: %.1fms\nReason: ElevenLabs HTTP %d",
                    latency_ms, resp.status_code
                )
                return await self.fallback_engine.synthesize(clean_text, **kwargs)

            audio_bytes = resp.content
            duration = max(0.5, len(clean_text) * 0.06)
            logger.info(
                "[TTS]\nProvider: ElevenLabs\nVoice: %s\nLatency: %.1fms",
                self.voice_id, latency_ms
            )
            return TTSResult(
                audio_data=audio_bytes,
                format="mp3",
                sample_rate=44100,
                duration_seconds=duration,
            )
        except Exception as exc:  # noqa: BLE001
            latency_ms = round((time.perf_counter() - start_t) * 1000, 1)
            logger.warning("[TTS]\nProvider: Local TTS (Fallback)\nVoice: Windows SAPI5\nLatency: %.1fms\nReason: %s", latency_ms, exc)
            return await self.fallback_engine.synthesize(clean_text, **kwargs)

    async def stream_speech(
        self, text_stream: AsyncIterator[str]
    ) -> AsyncIterator[bytes]:
        """Stream speech audio chunks as LLM text tokens arrive."""
        if not self.api_key:
            # Local fallback streaming
            full_text_list = []
            async for token in text_stream:
                full_text_list.append(token)
            full_text = "".join(full_text_list)
            res = await self.fallback_engine.synthesize(full_text)
            yield res.audio_data
            return

        # Buffer token chunks into sentence boundaries for fluid TTS generation
        buffer = []
        async for token in text_stream:
            buffer.append(token)
            accumulated = "".join(buffer)
            if any(accumulated.endswith(punct) for punct in (". ", "! ", "? ", "\n")):
                res = await self.synthesize(accumulated)
                if res.audio_data:
                    yield res.audio_data
                buffer.clear()

        if buffer:
            accumulated = "".join(buffer)
            res = await self.synthesize(accumulated)
            if res.audio_data:
                yield res.audio_data
