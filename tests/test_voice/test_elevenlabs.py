import pytest

from voice.base import TTSResult
from voice.elevenlabs import ElevenLabsTTSEngine
from voice.registry import VoiceProviderRegistry
from voice.service import VoiceService


@pytest.mark.asyncio
async def test_elevenlabs_unconfigured_fallback():
    # When api_key is empty/None, ElevenLabsTTSEngine should fall back to LocalTTSEngine
    engine = ElevenLabsTTSEngine(api_key="")
    result = await engine.synthesize("Hello ElevenLabs fallback test")

    assert isinstance(result, TTSResult)
    assert len(result.audio_data) > 0
    assert result.format == "wav"  # Local fallback produces WAV


@pytest.mark.asyncio
async def test_elevenlabs_stream_speech_fallback():
    engine = ElevenLabsTTSEngine(api_key="")

    async def token_generator():
        yield "Hello "
        yield "world!"

    audio_chunks = []
    async for chunk in engine.stream_speech(token_generator()):
        audio_chunks.append(chunk)

    assert len(audio_chunks) > 0
    assert len(audio_chunks[0]) > 0


@pytest.mark.asyncio
async def test_voice_provider_registry():
    assert "elevenlabs" in VoiceProviderRegistry.list_tts()
    assert "local" in VoiceProviderRegistry.list_tts()

    cls = VoiceProviderRegistry.get_tts("elevenlabs")
    assert cls == ElevenLabsTTSEngine


@pytest.mark.asyncio
async def test_voice_service_latency_tracking():
    service = VoiceService()
    res = await service.synthesize_speech("Test speech latency")
    assert res is not None
    assert service.last_tts_latency >= 0.0
