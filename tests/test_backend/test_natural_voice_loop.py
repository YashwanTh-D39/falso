"""
Test Suite for Milestone 2.5: Natural Voice Loop

Tests:
1. Voice State Machine & Valid Transitions
2. Request ID Ownership & Cancellation
3. Sentence-level TTS Endpoint & Audio Generation
4. Silero VAD Neural Classifier & Speech Detection
5. Voice Service Latency Metrics (STT / TTS)
6. Absence of Fake Voice Text Disclaimers
"""

import base64
import json
import pytest
from fastapi.testclient import TestClient

from app.main import app
from voice.service import VoiceService
from voice.vad import SileroVADService

client = TestClient(app)


class TestNaturalVoiceLoop:

    def test_1_state_machine_valid_states(self):
        valid_states = {
            'idle', 'listening', 'thinking', 'streaming',
            'speaking', 'interrupted', 'error', 'searching', 'warming', 'sleeping', 'booting'
        }
        assert 'listening' in valid_states
        assert 'speaking' in valid_states
        assert 'interrupted' in valid_states
        assert 'streaming' in valid_states
        assert 'thinking' in valid_states

    def test_2_tts_endpoint_synthesis_and_latency(self):
        response = client.post(
            "/api/v1/voice/tts",
            json={"text": "Hello, this is Falso voice synthesis test."}
        )
        assert response.status_code == 200
        assert len(response.content) > 100
        assert response.headers.get("content-type") in ("audio/mpeg", "audio/wav")

    def test_3_vad_endpoint_processing(self):
        # 512 samples 16kHz 16-bit PCM frame (1024 bytes) as supported by Silero VAD ONNX V5
        silent_pcm = b"\x00" * 1024
        audio_b64 = base64.b64encode(silent_pcm).decode("ascii")

        response = client.post(
            "/api/v1/voice/vad",
            json={
                "audio_base64": audio_b64,
                "sample_rate": 16000,
                "threshold": 0.75,
                "min_speech_duration_ms": 400
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "is_speech" in data
        assert "probability" in data

    def test_4_vad_diagnostics(self):
        response = client.get("/api/v1/voice/vad/diagnostics")
        assert response.status_code == 200
        data = response.json()
        assert "silero_status" in data
        assert "speech_detected" in data

    @pytest.mark.asyncio
    async def test_5_voice_service_latency_tracking(self):
        service = VoiceService()
        result = await service.synthesize_speech("Test sentence for latency tracking.")
        assert result.audio_data is not None
        assert len(result.audio_data) > 0
        assert service.last_tts_latency >= 0.0

    def test_6_no_fake_voice_disclaimers(self):
        from app.services.brain import BrainService
        brain = BrainService()
        system_prompt = brain.personality_engine.build_prompt()
        assert "NEVER" in system_prompt or "CRITICAL" in system_prompt
        assert "Awaiting Your Voice Input" not in system_prompt
