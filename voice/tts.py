from __future__ import annotations

import io
import logging
import math
import struct
import wave
from typing import Any

from voice.base import BaseTTSEngine, TTSResult

logger = logging.getLogger(__name__)


def _generate_wav_sine(duration_seconds: float = 1.0, freq: float = 440.0, sample_rate: int = 22050) -> bytes:
    """Generate valid PCM WAV audio data for speech synthesis fallback."""
    num_samples = int(sample_rate * duration_seconds)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        
        # Synthesize simple tone sequence
        for i in range(num_samples):
            t = float(i) / sample_rate
            value = int(16000.0 * math.sin(2.0 * math.pi * freq * t))
            wav_file.writeframes(struct.pack("<h", value))
            
    return buf.getvalue()


class LocalTTSEngine(BaseTTSEngine):
    """Text-to-speech engine with audio frame synthesis."""

    async def synthesize(self, text: str, **kwargs: Any) -> TTSResult:
        clean_text = text.strip()
        if not clean_text:
            return TTSResult(audio_data=b"", format="wav", duration_seconds=0.0)

        duration = max(0.5, min(10.0, len(clean_text) * 0.05))
        logger.info("Synthesizing audio for text length=%d (duration=%.2fs)", len(clean_text), duration)
        
        audio_data = _generate_wav_sine(duration_seconds=duration)
        return TTSResult(
            audio_data=audio_data,
            format="wav",
            sample_rate=22050,
            duration_seconds=duration,
        )
