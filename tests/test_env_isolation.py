from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.routes.system import is_placeholder_key, persist_settings_to_env
from config.settings import settings


def test_placeholder_key_detection():
    """Verify that placeholder API keys are correctly identified."""
    assert is_placeholder_key("test_key") is True
    assert is_placeholder_key("test_key_12345") is True
    assert is_placeholder_key("dummy") is True
    assert is_placeholder_key("example") is True
    assert is_placeholder_key("changeme") is True
    assert is_placeholder_key("your_api_key") is True

    # Real keys should not be marked as placeholder
    assert is_placeholder_key("AIzaSyD-1234567890abcdefghijklmnopqrst") is False


def test_test_suite_does_not_mutate_real_env():
    """Regression test: updating settings in test mode does NOT mutate the real .env file."""
    env_path = Path(".env")
    initial_content = env_path.read_text(encoding="utf-8") if env_path.is_file() else None

    with TestClient(app) as client:
        resp = client.post(
            "/api/v1/system/settings",
            json={
                "ai_provider": "gemini",
                "gemini_model": "gemini-3.6-flash",
                "gemini_api_key": "AIzaSyTestValidKey12345",
            },
        )
        assert resp.status_code == 200

    if env_path.is_file():
        current_content = env_path.read_text(encoding="utf-8")
        assert current_content == initial_content, "The real .env file was modified by test execution!"


def test_production_persistence_logic(tmp_path: Path):
    """Verify that production settings persist to a custom target .env file correctly."""
    temp_env = tmp_path / ".env"
    temp_env.write_text("AI_PROVIDER=gemini\nGEMINI_API_KEY=\nGEMINI_MODEL=gemini-1.5-flash\n", encoding="utf-8")

    # Set up test settings
    settings.ai_provider = "gemini"
    settings.gemini_model = "gemini-3.6-flash"
    settings.gemini_api_key = "AIzaSyValidProductionKey12345"

    success = persist_settings_to_env(settings, target_path=temp_env)
    assert success is True

    saved_text = temp_env.read_text(encoding="utf-8")
    assert "GEMINI_API_KEY=AIzaSyValidProductionKey12345" in saved_text
    assert "GEMINI_MODEL=gemini-3.6-flash" in saved_text


def test_placeholder_key_not_persisted_to_disk(tmp_path: Path):
    """Verify that placeholder keys are never written to disk."""
    temp_env = tmp_path / ".env"
    temp_env.write_text("AI_PROVIDER=gemini\nGEMINI_API_KEY=\nGEMINI_MODEL=gemini-1.5-flash\n", encoding="utf-8")

    # Set up test settings with a placeholder key
    settings.gemini_api_key = "test_key_12345"

    persist_settings_to_env(settings, target_path=temp_env)

    saved_text = temp_env.read_text(encoding="utf-8")
    # Should write empty key, never the placeholder!
    assert "GEMINI_API_KEY=\n" in saved_text
    assert "test_key_12345" not in saved_text
