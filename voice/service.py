from __future__ import annotations

import logging
import time
from collections.abc import AsyncIterator
from typing import Any

from config.settings import settings
from voice.base import AudioBuffer, BaseSTTEngine, BaseTTSEngine, STTResult, TTSResult
from voice.elevenlabs import ElevenLabsTTSEngine
from voice.registry import VoiceProviderRegistry
from voice.stt import LocalSTTEngine
from voice.tts import LocalTTSEngine

logger = logging.getLogger(__name__)

# Register engines at import time
VoiceProviderRegistry.register_tts("local", LocalTTSEngine)
VoiceProviderRegistry.register_tts("elevenlabs", ElevenLabsTTSEngine)
VoiceProviderRegistry.register_stt("local", LocalSTTEngine)


class VoiceService:
    """Unified manager for voice input (STT), voice output (TTS), and latency metrics."""

    def __init__(
        self,
        stt_engine: BaseSTTEngine | None = None,
        tts_engine: BaseTTSEngine | None = None,
    ) -> None:
        self.stt_engine = stt_engine or LocalSTTEngine()
        if tts_engine is not None:
            self.tts_engine = tts_engine
        elif settings.elevenlabs_api_key:
            self.tts_engine = ElevenLabsTTSEngine()
        else:
            self.tts_engine = LocalTTSEngine()

        self.last_stt_latency: float = 0.0
        self.last_tts_latency: float = 0.0

    async def transcribe_audio(self, audio: AudioBuffer | bytes, **kwargs: Any) -> STTResult:
        """Convert speech audio into text, tracking STT latency."""
        start = time.perf_counter()
        result = await self.stt_engine.transcribe(audio, **kwargs)
        self.last_stt_latency = time.perf_counter() - start
        logger.info("STT completed in %.3fs", self.last_stt_latency)
        return result

    async def synthesize_speech(self, text: str, **kwargs: Any) -> TTSResult:
        """Convert response text into synthesized speech audio, tracking TTS latency."""
        start = time.perf_counter()
        result = await self.tts_engine.synthesize(text, **kwargs)
        self.last_tts_latency = time.perf_counter() - start
        logger.info("TTS completed in %.3fs (%s format)", self.last_tts_latency, result.format)
        return result

    async def stream_speech(
        self, text_stream: AsyncIterator[str]
    ) -> AsyncIterator[bytes]:
        """Stream synthesized audio bytes directly as LLM text tokens arrive."""
        if hasattr(self.tts_engine, "stream_speech"):
            async for chunk in self.tts_engine.stream_speech(text_stream):
                yield chunk
        else:
            # Fallback for engines without native token streaming
            full_text_list = []
            async for token in text_stream:
                full_text_list.append(token)
            res = await self.synthesize_speech("".join(full_text_list))
            yield res.audio_data
