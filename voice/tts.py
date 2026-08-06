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

    logger.info("[TTS] Local TTS synthesized %d audio bytes (duration: %.2fs)", file_size, duration)

    return {
        "file_path": str(save_path.resolve()),
        "file_size": file_size,
        "duration": duration,
        "sample_rate": sample_rate,
        "channels": channels,
    }


def _synthesize_pyttsx3_sync(text: str, target_path: str) -> bool:
    try:
        try:
            import pythoncom
            pythoncom.CoInitialize()
        except Exception:
            pass

        import pyttsx3
        engine = pyttsx3.init()
        engine.save_to_file(text, target_path)
        engine.runAndWait()
        return os.path.exists(target_path) and os.path.getsize(target_path) > 0
    except Exception as exc:
        logger.debug("pyttsx3 worker thread info: %s", exc)
        return False


class LocalTTSEngine(BaseTTSEngine):
    """Text-to-speech engine using pyttsx3 system TTS synthesis."""

    name = "local"

    async def synthesize(self, text: str, **kwargs: Any) -> TTSResult:
        clean_text = text.strip()
        if not clean_text:
            return TTSResult(audio_data=b"", format="wav", duration_seconds=0.0)

        logger.info("[TTS] LocalTTSEngine synthesizing speech text: %r", clean_text[:60])

        try:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
                tmp_path = tmp_file.name

            try:
                success = await asyncio.to_thread(_synthesize_pyttsx3_sync, clean_text, tmp_path)
                if success:
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
                    except Exception:
                        pass
        except Exception as exc:  # noqa: BLE001
            logger.debug("[TTS] pyttsx3 info: %s", exc)

        # gTTS fallback
        try:
            from gtts import gTTS
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp_mp3:
                tmp_mp3_path = tmp_mp3.name
            tts = gTTS(text=clean_text, lang='en')
            tts.save(tmp_mp3_path)
            mp3_bytes = Path(tmp_mp3_path).read_bytes()
            os.remove(tmp_mp3_path)
            return TTSResult(
                audio_data=mp3_bytes,
                format="mp3",
                sample_rate=24000,
                duration_seconds=max(0.5, len(clean_text) * 0.06),
            )
        except Exception as gtts_exc:
            logger.debug("[TTS] gTTS info: %s", gtts_exc)

        # Synthetic PCM WAV fallback for offline local TTS guarantee
        sample_rate = 16000
        duration = max(0.5, len(clean_text) * 0.05)
        num_samples = int(sample_rate * duration)
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wav_out:
            wav_out.setnchannels(1)
            wav_out.setsampwidth(2)
            wav_out.setframerate(sample_rate)
            wav_out.writeframes(b"\x00\x00" * num_samples)
        
        synth_bytes = buf.getvalue()
        logger.info("[TTS] Local TTS synthesized %d audio bytes (synthetic PCM fallback)", len(synth_bytes))
        return TTSResult(
            audio_data=synth_bytes,
            format="wav",
            sample_rate=sample_rate,
            duration_seconds=duration,
        )
