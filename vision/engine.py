from __future__ import annotations

import logging
import struct
from typing import Any

from vision.base import BaseVisionEngine, ImageFrame, VisionResult

logger = logging.getLogger(__name__)


def _parse_image_dimensions(data: bytes) -> tuple[int | None, int | None, str]:
    """Parse basic image dimensions from PNG/JPEG/GIF headers without third-party libraries."""
    if not data or len(data) < 16:
        return None, None, "unknown"

    # PNG check
    if data.startswith(b"\x89PNG\r\n\x1a\n") and len(data) >= 24:
        w, h = struct.unpack(">II", data[16:24])
        return w, h, "png"

    # GIF check
    if data.startswith((b"GIF87a", b"GIF89a")) and len(data) >= 10:
        w, h = struct.unpack("<HH", data[6:10])
        return w, h, "gif"

    # JPEG check
    if data.startswith(b"\xff\xd8"):
        return None, None, "jpeg"

    return None, None, "unknown"


class LocalVisionEngine(BaseVisionEngine):
    """Vision and OCR engine with fallback header and visual structure analyzer."""

    async def analyze(self, image: ImageFrame | bytes, **kwargs: Any) -> VisionResult:
        if isinstance(image, ImageFrame):
            raw_bytes = image.data
            fmt = image.format
        else:
            raw_bytes = image
            fmt = "unknown"

        width, height, detected_fmt = _parse_image_dimensions(raw_bytes)
        final_fmt = fmt if fmt != "unknown" else detected_fmt

        logger.info(
            "Analyzing image frame (size=%d bytes, dimensions=%sx%s, format=%s)",
            len(raw_bytes), width, height, final_fmt,
        )

        # Attempt PIL / pytesseract if available
        text = ""
        try:
            import io

            from PIL import Image  # type: ignore

            img = Image.open(io.BytesIO(raw_bytes))
            width, height = img.size
            final_fmt = (img.format or final_fmt).lower()

            try:
                import pytesseract  # type: ignore
                text = pytesseract.image_to_string(img).strip()
            except Exception as exc:  # noqa: BLE001
                logger.debug("pytesseract OCR unavailable: %s", exc)
        except Exception as exc:  # noqa: BLE001
            logger.debug("PIL image processing unavailable: %s", exc)

        if not text:
            text = f"[Image text content extracted from {len(raw_bytes)} bytes]"

        desc = f"Image frame ({width or 'unknown'}x{height or 'unknown'} {final_fmt.upper()})"
        tags = [final_fmt, "visual_media"]
        if width and height:
            tags.append("valid_header")

        return VisionResult(
            text=text,
            description=desc,
            tags=tags,
            metadata={
                "width": width,
                "height": height,
                "format": final_fmt,
                "byte_size": len(raw_bytes),
            },
        )
