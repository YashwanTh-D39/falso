import pytest
from fastapi.testclient import TestClient

from app.main import app
from voice import (
    AudioBuffer,
    VoiceConfig,
    VoiceConversationOrchestrator,
    WebAudioHTTPTransport,
)


@pytest.mark.asyncio
async def test_voice_conversation_orchestrator_turn():
    orchestrator = VoiceConversationOrchestrator()
    audio_in = AudioBuffer(data=b"\x00\x01" * 16000)

    audio_chunks = []
    async for chunk in orchestrator.process_voice_turn(audio_in):
        audio_chunks.append(chunk)

    assert len(audio_chunks) > 0
    assert len(audio_chunks[0]) > 0


@pytest.mark.asyncio
async def test_voice_config_and_transport():
    config = VoiceConfig(
        voice_id="21m00Tcm4TlvDq8ikWAM",
        wake_word="Hey Falso",
        emotion_style="empathetic",
    )
    assert config.wake_word == "Hey Falso"
    assert config.emotion_style == "empathetic"

    transport = WebAudioHTTPTransport()
    await transport.interrupt()
    assert transport.interrupted is True


def test_voice_conversation_endpoint():
    with TestClient(app) as client:
        r = client.post("/api/v1/voice/conversation", content=b"\x00\x01" * 3200)
        assert r.status_code == 200
        assert len(r.content) > 0
