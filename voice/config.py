from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class VoiceConfig:
    """Configuration container for intelligent voice conversations, supporting
    future features (wake word, emotion, multiple personalities, offline models).
    """

    voice_id: str = "21m00Tcm4TlvDq8ikWAM"
    personality_id: str = "default"
    wake_word: str = "Hey Falso"
    wake_word_enabled: bool = False
    emotion_style: str = "neutral"  # e.g., neutral, excited, empathetic, professional
    speaking_rate: float = 1.0
    pitch: float = 1.0
    stability: float = 0.5
    similarity_boost: float = 0.75
    metadata: dict[str, Any] = field(default_factory=dict)
