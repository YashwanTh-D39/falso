from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class AudioBuffer:
    data: bytes
    sample_rate: int = 16000
    channels: int = 1
    sample_width: int = 2  # 16-bit PCM


@dataclass
class STTResult:
    text: str
    confidence: float = 1.0
    language: str = "en"
    duration_seconds: float = 0.0


@dataclass
class TTSResult:
    audio_data: bytes
    format: str = "wav"
    sample_rate: int = 22050
    duration_seconds: float = 0.0


class BaseSTTEngine(ABC):
    """Abstract interface for Speech-to-Text engines."""

    @abstractmethod
    async def transcribe(self, audio: AudioBuffer | bytes, **kwargs: Any) -> STTResult:
        pass


class BaseTTSEngine(ABC):
    """Abstract interface for Text-to-Speech engines."""

    @abstractmethod
    async def synthesize(self, text: str, **kwargs: Any) -> TTSResult:
        pass
