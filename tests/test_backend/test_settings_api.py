from fastapi.testclient import TestClient

from app.main import app
from config.settings import settings


def test_get_settings_endpoint():
    with TestClient(app) as client:
        response = client.get("/api/v1/system/settings")
        assert response.status_code == 200
        data = response.json()
        assert "ai_provider" in data
        assert "gemini_model" in data
        assert "gemini_api_key_configured" in data


def test_update_settings_endpoint():
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/system/settings",
            json={
                "ai_provider": "gemini",
                "gemini_model": "gemini-3.6-flash",
                "gemini_api_key": "AIzaSyTestValidKey12345",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "updated"
        assert data["ai_provider"] == "gemini"
        assert data["gemini_model"] == "gemini-3.6-flash"
        assert data["gemini_api_key_configured"] is True

        assert settings.ai_provider == "gemini"
        assert settings.gemini_api_key == "AIzaSyTestValidKey12345"


def test_discover_models_endpoint():
    with TestClient(app) as client:
        response = client.get("/api/v1/system/models")
        assert response.status_code == 200
        data = response.json()
        assert "models" in data
        assert isinstance(data["models"], list)
        assert len(data["models"]) > 0


def test_test_connection_endpoint():
    with TestClient(app) as client:
        response = client.post("/api/v1/system/test-connection")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "message" in data


def test_elevenlabs_settings_update():
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/system/settings",
            json={
                "elevenlabs_api_key": "el_valid_key_123456789",
                "elevenlabs_voice_id": "21m00Tcm4TlvDq8ikWAM",
                "tts_provider": "elevenlabs",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "updated"
        assert data["elevenlabs_api_key_configured"] is True
        assert data["elevenlabs_voice_id"] == "21m00Tcm4TlvDq8ikWAM"
        assert data["tts_provider"] == "elevenlabs"

        # Verify Gemini settings remain preserved
        assert settings.gemini_model == "gemini-3.6-flash"


def test_discover_voices_endpoint():
    with TestClient(app) as client:
        response = client.get("/api/v1/system/voices")
        assert response.status_code == 200
        data = response.json()
        assert "voices" in data
        assert isinstance(data["voices"], list)
        assert len(data["voices"]) > 0
        assert "voice_id" in data["voices"][0]
        assert "name" in data["voices"][0]
