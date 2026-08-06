import logging
from app.services.server_verifier import (
    check_port_active,
    detect_active_falso_server,
    temporary_verification_server,
    validate_code_static,
)


def test_static_code_validation():
    """Verify syntax checking without launching Uvicorn."""
    res = validate_code_static(["app/main.py", "config/settings.py"])
    assert res is True


def test_detect_active_server():
    """Verify server port detection logic."""
    port = detect_active_falso_server()
    assert port is None or isinstance(port, int)


def test_temporary_verification_server_lifecycle(caplog):
    """Verify server context manager lifecycle logging and immediate cleanup."""
    caplog.set_level(logging.INFO)
    with temporary_verification_server(port=8998) as base_url:
        assert "http://127.0.0.1" in base_url

    logs = caplog.text
    assert "[SERVER] Server started" in logs or "[SERVER] Existing FALSO server detected" in logs
    assert "[SERVER] Verification complete" in logs
    assert "[SERVER] Server stopped" in logs or "reusing instance" in logs
