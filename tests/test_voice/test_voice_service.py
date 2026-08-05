import pytest

from voice.base import AudioBuffer
from voice.service import VoiceService


@pytest.mark.asyncio
async def test_stt_transcription():
    service = VoiceService()
    audio = AudioBuffer(data=b"\x00\x01" * 16000, sample_rate=16000)
    
    result = await service.transcribe_audio(audio)
    assert result.confidence > 0.0
    assert result.duration_seconds > 0.0
    assert len(result.text) > 0


@pytest.mark.asyncio
async def test_tts_synthesis():
    service = VoiceService()
    result = await service.synthesize_speech("Hello, I am Falso.")
    
    assert result.format == "wav"
    assert len(result.audio_data) > 44  # Valid WAV header + payload is >44 bytes
    assert result.duration_seconds > 0.0
    assert result.audio_data.startswith(b"RIFF")
