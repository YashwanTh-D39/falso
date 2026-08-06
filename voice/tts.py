from __future__ import annotations

import asyncio
import logging
import os
import tempfile
from pathlib import Path
from typing import Any

from voice.base import BaseTTSEngine, TTSResult

logger = logging.getLogger(__name__)


class LocalTTSEngine(BaseTTSEngine):
    """Text-to-speech engine using pyttsx3 system TTS synthesis."""

    name = "local"

    async def synthesize(self, text: str, **kwargs: Any) -> TTSResult:
        clean_text = text.strip()
        if not clean_text:
            return TTSResult(audio_data=b"", format="wav", duration_seconds=0.0)

        logger.info("[TTS AUDIT Stage 5] LocalTTSEngine synthesizing speech text: %r", clean_text[:60])

        try:
            import pyttsx3

            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
                tmp_path = tmp_file.name

            try:
                engine = pyttsx3.init()
                engine.save_to_file(clean_text, tmp_path)
                engine.runAndWait()

                if os.path.exists(tmp_path) and os.path.getsize(tmp_path) > 0:
                    audio_bytes = await asyncio.to_thread(Path(tmp_path).read_bytes)
                    duration = max(0.5, len(audio_bytes) / 44100.0)
                    logger.info(
                        "[TTS AUDIT Stage 6] LocalTTSEngine generated %d audio bytes (WAV spoken audio)",
                        len(audio_bytes),
                    )
                    return TTSResult(
                        audio_data=audio_bytes,
                        format="wav",
                        sample_rate=22050,
                        duration_seconds=duration,
                    )
            finally:
                if os.path.exists(tmp_path):
                    try:
                        os.remove(tmp_path)
                    except Exception as exc:  # noqa: BLE001
                        logger.debug("Could not cleanup temp WAV file: %s", exc)
        except Exception as exc:  # noqa: BLE001
            logger.warning("[TTS AUDIT Stage 5 Failure] pyttsx3 local synthesis failed (%s)", exc)

        return TTSResult(
            audio_data=b"",
            format="wav",
            sample_rate=22050,
            duration_seconds=0.0,
        )
