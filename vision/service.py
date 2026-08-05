from __future__ import annotations

import logging
from typing import Any

from vision.base import BaseVisionEngine, ImageFrame, VisionResult
from vision.engine import LocalVisionEngine

logger = logging.getLogger(__name__)


class VisionService:
    """Unified manager for image analysis and OCR text extraction."""

    def __init__(self, engine: BaseVisionEngine | None = None) -> None:
        self.engine = engine or LocalVisionEngine()

    async def analyze_image(self, image: ImageFrame | bytes, **kwargs: Any) -> VisionResult:
        """Perform comprehensive visual analysis on an image."""
        return await self.engine.analyze(image, **kwargs)

    async def extract_text(self, image: ImageFrame | bytes, **kwargs: Any) -> str:
        """Perform OCR on an image and return extracted text string."""
        result = await self.analyze_image(image, **kwargs)
        return result.text
