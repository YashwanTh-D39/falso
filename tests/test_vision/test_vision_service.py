import pytest

from vision.base import ImageFrame
from vision.service import VisionService

# Sample 1x1 PNG image bytes for testing
MINIMAL_PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\rIDATx\x9cc`\x00\x00\x00"
    b"\x02\x00\x01H\xaf\xa4q\x00\x00\x00\x00IEND\xaeB`\x82"
)


@pytest.mark.asyncio
async def test_vision_image_analysis():
    service = VisionService()
    frame = ImageFrame(data=MINIMAL_PNG_BYTES, format="png")
    
    result = await service.analyze_image(frame)
    assert result.metadata["width"] == 1
    assert result.metadata["height"] == 1
    assert result.metadata["format"] == "png"
    assert "png" in result.tags


@pytest.mark.asyncio
async def test_vision_extract_text():
    service = VisionService()
    text = await service.extract_text(MINIMAL_PNG_BYTES)
    assert isinstance(text, str)
    assert len(text) > 0
