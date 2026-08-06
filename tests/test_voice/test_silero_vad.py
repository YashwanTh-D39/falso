from __future__ import annotations

import base64

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.main import app
from voice.vad import SileroVADService


@pytest.fixture
def client():
    return TestClient(app)


def test_silero_vad_service_init():
    service = SileroVADService(threshold=0.75, min_speech_duration_ms=400)
    assert "ACTIVE" in service.status or "LOADED" in service.status
    diag = service.get_diagnostics()
    assert "silero_status" in diag
    assert "non_speech_ignored" in diag
    assert "interrupt_triggered" in diag


def test_silero_vad_silence_chunk():
    service = SileroVADService(threshold=0.75, min_speech_duration_ms=400)
    silence_pcm = np.zeros(512, dtype=np.int16).tobytes()
    res = service.process_pcm_chunk(silence_pcm, sample_rate=16000)
    assert res["is_speech"] is False
    assert res["probability"] < 0.20
    assert res["interrupt"] is False
    assert res["diagnostics"]["non_speech_ignored"] >= 1


def test_silero_vad_base64_audio():
    service = SileroVADService(threshold=0.75, min_speech_duration_ms=400)
    silence_pcm = np.zeros(512, dtype=np.int16).tobytes()
    b64_audio = base64.b64encode(silence_pcm).decode("utf-8")
    res = service.process_base64_pcm(b64_audio, sample_rate=16000)
    assert res["is_speech"] is False
    assert res["interrupt"] is False


def test_silero_vad_api_endpoint(client):
    silence_pcm = np.zeros(512, dtype=np.int16).tobytes()
    b64_audio = base64.b64encode(silence_pcm).decode("utf-8")
    response = client.post(
        "/api/v1/voice/vad",
        json={
            "audio_base64": b64_audio,
            "sample_rate": 16000,
            "threshold": 0.75,
            "min_speech_duration_ms": 400,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "is_speech" in data
    assert "probability" in data
    assert "interrupt" in data
    assert "diagnostics" in data


def test_silero_vad_diagnostics_endpoint(client):
    response = client.get("/api/v1/voice/vad/diagnostics")
    assert response.status_code == 200
    data = response.json()
    assert "silero_status" in data
    assert "speech_detected" in data
    assert "non_speech_ignored" in data
    assert "interrupt_triggered" in data
