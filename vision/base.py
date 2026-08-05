from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass
class ImageFrame:
    data: bytes
    format: str = "png"
    width: int | None = None
    height: int | None = None


@dataclass
class VisionResult:
    text: str = ""
    description: str = ""
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(
        default_factory=lambda: datetime.now(UTC).isoformat()
    )


class BaseVisionEngine(ABC):
    """Abstract interface for image processing and OCR vision engines."""

    @abstractmethod
    async def analyze(self, image: ImageFrame | bytes, **kwargs: Any) -> VisionResult:
        pass
