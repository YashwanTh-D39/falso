"""Unit tests for BootTracker startup instrumentation."""

import pytest
import time
from app.services.boot_tracker import boot_tracker


def test_boot_tracker_stages():
    boot_tracker.log_stage(1, 0.05, "Config loaded")
    assert boot_tracker.current_stage == 1
    assert boot_tracker.stage_results[1]["duration_sec"] == 0.05

    boot_tracker.log_stage(2, 0.10, "DB init")
    assert boot_tracker.current_stage == 2


def test_boot_tracker_warning_threshold(caplog):
    with caplog.at_level("WARNING"):
        boot_tracker.log_stage(3, 2.50, "Slow Ollama connection")
        assert "exceeds 2s threshold" in caplog.text


def test_boot_status_diagnostics():
    status = boot_tracker.get_boot_status()
    assert "stages" in status
    assert len(status["stages"]) == 10
