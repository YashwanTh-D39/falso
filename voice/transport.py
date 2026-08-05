from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator


class BaseVoiceTransport(ABC):
    """Abstract interface for audio transport layers (WebAudio, WebRTC, WebSockets, SIP/Phone calls)."""

    @abstractmethod
    async def send_audio_chunk(self, chunk: bytes) -> None:
        """Deliver synthesized audio chunk to client destination."""

    @abstractmethod
    async def receive_audio_stream(self) -> AsyncIterator[bytes]:
        """Stream incoming audio bytes from client microphone or call stream."""

    @abstractmethod
    async def interrupt(self) -> None:
        """Signal immediate barge-in interrupt to abort ongoing audio playback."""


class WebAudioHTTPTransport(BaseVoiceTransport):
    """Standard HTTP/SSE Web Audio transport for web browser UI."""

    def __init__(self) -> None:
        self.interrupted = False

    async def send_audio_chunk(self, chunk: bytes) -> None:
        pass

    async def receive_audio_stream(self) -> AsyncIterator[bytes]:
        yield b""

    async def interrupt(self) -> None:
        self.interrupted = True
