from __future__ import annotations

import base64
import logging
from typing import Any

import numpy as np
import torch

logger = logging.getLogger(__name__)


class SileroVADService:
    """Silero VAD Neural Speech Detection Service.
    
    Uses Silero VAD ONNX model to classify audio frames as human speech vs non-speech
    (fan noise, TV audio, music, keyboard clicks, mouse snaps, door bumps, background static).
    """

    def __init__(self, threshold: float = 0.75, min_speech_duration_ms: int = 400) -> None:
        self.default_threshold = threshold
        self.default_min_speech_duration_ms = min_speech_duration_ms
        self.status = "INITIALIZING"
        self.model = None
        self.speech_detected_count = 0
        self.non_speech_ignored_count = 0
        self.interrupt_triggered_count = 0
        self.speech_duration_ms = 0.0
        self.last_is_speech = False
        self.last_prob = 0.0
        self._init_model()

    def _init_model(self) -> None:
        try:
            import silero_vad
            self.model = silero_vad.load_silero_vad(onnx=True)
            self.status = "ACTIVE (Silero ONNX V5)"
            logger.info("Silero VAD ONNX model loaded successfully")
        except (ImportError, RuntimeError, ValueError, OSError) as exc:
            logger.warning("Failed to load Silero ONNX model, falling back to JIT: %s", exc)
            try:
                import silero_vad
                self.model = silero_vad.load_silero_vad(onnx=False)
                self.status = "ACTIVE (Silero Torch JIT)"
                logger.info("Silero VAD Torch JIT model loaded successfully")
            except (ImportError, RuntimeError, ValueError, OSError) as j_exc:
                logger.error("Failed to load Silero VAD model: %s", j_exc)
                self.status = "ERROR (Model Load Failed)"

    def process_pcm_chunk(
        self,
        pcm_bytes: bytes,
        sample_rate: int = 16000,
        threshold: float | None = None,
        min_speech_duration_ms: int | None = None,
    ) -> dict[str, Any]:
        target_threshold = threshold if threshold is not None else self.default_threshold
        target_min_duration = (
            min_speech_duration_ms
            if min_speech_duration_ms is not None
            else self.default_min_speech_duration_ms
        )

        if self.model is None or not pcm_bytes:
            return {
                "is_speech": False,
                "probability": 0.0,
                "speech_duration_ms": 0,
                "interrupt": False,
                "diagnostics": self.get_diagnostics(),
            }

        try:
            # Parse raw PCM 16-bit signed integers or float32 bytes
            if len(pcm_bytes) % 2 == 0:
                audio_np = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32) / 32768.0
            else:
                audio_np = np.frombuffer(pcm_bytes, dtype=np.float32)

            if len(audio_np) == 0:
                return {
                    "is_speech": False,
                    "probability": 0.0,
                    "speech_duration_ms": 0,
                    "interrupt": False,
                    "diagnostics": self.get_diagnostics(),
                }

            # Silero VAD expects a 1D tensor audio chunk (e.g. 512 samples at 16kHz)
            audio_tensor = torch.from_numpy(audio_np)
            speech_prob = float(self.model(audio_tensor, sample_rate).item())
            
            self.last_prob = speech_prob
            is_speech = speech_prob >= target_threshold
            self.last_is_speech = is_speech

            frame_ms = (len(audio_np) / sample_rate) * 1000.0
            interrupt_triggered = False

            if is_speech:
                self.speech_detected_count += 1
                self.speech_duration_ms += frame_ms
                if self.speech_duration_ms >= target_min_duration:
                    interrupt_triggered = True
                    self.interrupt_triggered_count += 1
                    self.speech_duration_ms = 0.0
            else:
                # Non-speech sound (fan, TV, music, keyboard, mouse, static) ignored!
                self.non_speech_ignored_count += 1
                self.speech_duration_ms = 0.0

            return {
                "is_speech": is_speech,
                "probability": round(speech_prob, 4),
                "speech_duration_ms": int(self.speech_duration_ms),
                "interrupt": interrupt_triggered,
                "diagnostics": self.get_diagnostics(),
            }

        except (RuntimeError, ValueError, TypeError, AttributeError, OSError) as exc:
            logger.error("Error running Silero VAD processing: %s", exc)
            return {
                "is_speech": False,
                "probability": 0.0,
                "speech_duration_ms": 0,
                "interrupt": False,
                "error": str(exc),
                "diagnostics": self.get_diagnostics(),
            }

    def process_base64_pcm(
        self,
        base64_str: str,
        sample_rate: int = 16000,
        threshold: float | None = None,
        min_speech_duration_ms: int | None = None,
    ) -> dict[str, Any]:
        try:
            pcm_bytes = base64.b64decode(base64_str)
            return self.process_pcm_chunk(
                pcm_bytes,
                sample_rate=sample_rate,
                threshold=threshold,
                min_speech_duration_ms=min_speech_duration_ms,
            )
        except (ValueError, TypeError, OSError) as exc:
            return {
                "is_speech": False,
                "probability": 0.0,
                "speech_duration_ms": 0,
                "interrupt": False,
                "error": f"Base64 decode failed: {exc}",
                "diagnostics": self.get_diagnostics(),
            }

    def get_diagnostics(self) -> dict[str, Any]:
        return {
            "silero_status": self.status,
            "speech_detected": self.last_is_speech,
            "speech_probability": round(self.last_prob, 4),
            "non_speech_ignored": self.non_speech_ignored_count,
            "interrupt_triggered": self.interrupt_triggered_count,
            "speech_duration_ms": int(self.speech_duration_ms),
        }
