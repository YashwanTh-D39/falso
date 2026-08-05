from __future__ import annotations

import logging
from typing import ClassVar

from voice.base import BaseSTTEngine, BaseTTSEngine

logger = logging.getLogger(__name__)


class VoiceProviderRegistry:
    """Registry for extensible Speech-to-Text and Text-to-Speech engines."""

    _tts_engines: ClassVar[dict[str, type[BaseTTSEngine]]] = {}
    _stt_engines: ClassVar[dict[str, type[BaseSTTEngine]]] = {}

    @classmethod
    def register_tts(cls, name: str, engine_cls: type[BaseTTSEngine]) -> type[BaseTTSEngine]:
        cls._tts_engines[name.lower()] = engine_cls
        logger.debug("Registered TTS engine: %s", name)
        return engine_cls

    @classmethod
    def register_stt(cls, name: str, engine_cls: type[BaseSTTEngine]) -> type[BaseSTTEngine]:
        cls._stt_engines[name.lower()] = engine_cls
        logger.debug("Registered STT engine: %s", name)
        return engine_cls

    @classmethod
    def get_tts(cls, name: str) -> type[BaseTTSEngine] | None:
        return cls._tts_engines.get(name.lower())

    @classmethod
    def get_stt(cls, name: str) -> type[BaseSTTEngine] | None:
        return cls._stt_engines.get(name.lower())

    @classmethod
    def list_tts(cls) -> list[str]:
        return list(cls._tts_engines.keys())

    @classmethod
    def list_stt(cls) -> list[str]:
        return list(cls._stt_engines.keys())
