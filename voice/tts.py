from __future__ import annotations

import asyncio
import io
import logging
import os
import tempfile
import wave
import winsound
from pathlib import Path
from typing import Any

from voice.base import BaseTTSEngine, TTSResult

logger = logging.getLogger(__name__)

_tts_counter = 0
_debug_dir = Path("logs/tts_debug")
_debug_dir.mkdir(parents=True, exist_ok=True)


def _save_and_verify_wav(audio_bytes: bytes) -> dict[str, Any]:
    global _tts_counter
    _tts_counter += 1
    file_name = f"tts_{_tts_counter:03d}.wav"
    save_path = _debug_dir / file_name

    save_path.write_bytes(audio_bytes)
    file_size = len(audio_bytes)

    channels, sample_rate, duration = 1, 22050, 0.0
    try:
        with wave.open(io.BytesIO(audio_bytes), "rb") as wav_in:
            channels = wav_in.getnchannels()
            sample_rate = wav_in.getframerate()
            frames = wav_in.getnframes()
            duration = frames / float(sample_rate) if sample_rate else 0.0
    except Exception as exc:  # noqa: BLE001
        logger.debug("Could not parse WAV header: %s", exc)

    logger.info(
        "[TTS DIAGNOSTICS] Saved debug WAV -> Path: %s | Size: %d bytes | Duration: %.2fs | Sample Rate: %d Hz | Channels: %d",
        save_path.resolve(),
        file_size,
        duration,
        sample_rate,
        channels,
    )

    # Play backend audio locally via winsound
    try:
        winsound.PlaySound(str(save_path.resolve()), winsound.SND_FILENAME | winsound.SND_ASYNC)
        logger.info("[TTS DIAGNOSTICS] Playing saved WAV locally on backend speaker via winsound: %s", save_path.name)
    except Exception as exc:  # noqa: BLE001
        logger.warning("[TTS DIAGNOSTICS] Local winsound playback failed: %s", exc)

    return {
        "file_path": str(save_path.resolve()),
        "file_size": file_size,
        "duration": duration,
        "sample_rate": sample_rate,
        "channels": channels,
    }


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
                    info = _save_and_verify_wav(audio_bytes)

                    return TTSResult(
                        audio_data=audio_bytes,
                        format="wav",
                        sample_rate=info["sample_rate"],
                        duration_seconds=info["duration"],
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
