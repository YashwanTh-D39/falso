from __future__ import annotations

import logging
from typing import Any

from voice.base import AudioBuffer, BaseSTTEngine, BaseTTSEngine, STTResult, TTSResult
from voice.stt import LocalSTTEngine
from voice.tts import LocalTTSEngine

logger = logging.getLogger(__name__)


class VoiceService:
    """Unified manager for voice input (STT) and voice output (TTS)."""

    def __init__(
        self,
        stt_engine: BaseSTTEngine | None = None,
        tts_engine: BaseTTSEngine | None = None,
    ) -> None:
        self.stt_engine = stt_engine or LocalSTTEngine()
        self.tts_engine = tts_engine or LocalTTSEngine()

    async def transcribe_audio(self, audio: AudioBuffer | bytes, **kwargs: Any) -> STTResult:
        """Convert speech audio into text."""
        return await self.stt_engine.transcribe(audio, **kwargs)

    async def synthesize_speech(self, text: str, **kwargs: Any) -> TTSResult:
        """Convert response text into synthesized speech audio."""
        return await self.tts_engine.synthesize(text, **kwargs)
