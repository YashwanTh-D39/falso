"""Unit tests for SystemMonitorService and FilesystemIndexerService."""

import pytest
import os
from pathlib import Path
from app.services.system_monitor import system_monitor
from app.services.filesystem_indexer import filesystem_indexer
from app.services.permission_service import permission_service


def test_system_monitor_stats():
    stats = system_monitor.get_system_stats()
    assert "cpu" in stats
    assert "ram" in stats
    assert "disks" in stats
    assert "network" in stats
    assert stats["cpu"]["logical_cores"] >= 1


def test_system_monitor_processes():
    procs = system_monitor.get_running_processes(limit=10)
    assert isinstance(procs, list)
    if procs:
        p = procs[0]
        assert "pid" in p
        assert "name" in p


def test_permission_service_path_checking():
    allowed_desktop = str(Path.home() / "Desktop" / "sample.txt")
    assert permission_service.is_path_allowed(allowed_desktop) is True

    forbidden_path = "c:/Windows/System32/config/SAM"
    assert permission_service.is_path_allowed(forbidden_path) is False


def test_permission_token_lifecycle():
    token = permission_service.create_confirmation_token("delete_file", "sample.txt")
    assert token is not None
    data = permission_service.confirm_token(token)
    assert data is not None
    assert data["action"] == "delete_file"
    # Second confirm should yield None as token was consumed
    assert permission_service.confirm_token(token) is None
