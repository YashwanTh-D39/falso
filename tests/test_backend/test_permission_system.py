"""
Test Suite for Milestone 2.7: Capability-Based Permission System & PC Access Control

Tests exact acceptance cases:
1. Application Allowlist Check: "Open Calculator." (PASS)
2. Sandbox Directory Access: "Open Project-Falso." (PASS)
3. Sandbox File Read: "Read app/main.py." (PASS)
4. Protected Directory Block: "Delete C:\\Windows\\System32\\test.dll." (DENY)
5. Secrets Protection: "Read my NVIDIA API key from .env." (DENY exposing secret to model)
6. Approved Command Registry: "Run pytest in Project-Falso." (PASS)
7. Unapproved Arbitrary Shell Command: "Run an arbitrary PowerShell command." (DENY)
8. High-Impact Action Confirmation: "Send an email to John." (REQUIRES CONFIRMATION)
9. Emergency Lockdown Activation: "FALSO lockdown." (PASS - disables all execution capabilities)
"""

import json
import pytest

from app.services.automation.permissions import (
    FileOperation,
    PermissionLevel,
    permission_manager,
)
from app.services.brain import BrainService


class FakePermProvider:
    name = "fake"
    model = "fake-model"

    async def stream_chat(self, messages: list[dict], **kwargs):
        yield type("Chunk", (), {"text": "Executed cleanly."})()


class TestPermissionSystem:

    def setup_method(self):
        permission_manager.disable_lockdown()

    def test_1_open_calculator_allowlist(self):
        res = permission_manager.check_application_launch("Calculator")
        assert res.allowed is True
        assert "approved allowlist" in res.reason

    def test_2_open_project_falso_sandbox(self):
        res = permission_manager.check_filesystem_access(
            r"C:\Users\Admin\Project-Falso",
            operation=FileOperation.READ
        )
        assert res.allowed is True

    def test_3_read_main_py_in_sandbox(self):
        res = permission_manager.check_filesystem_access(
            r"C:\Users\Admin\Project-Falso\app\main.py",
            operation=FileOperation.READ
        )
        assert res.allowed is True

    def test_4_delete_windows_system32_dll_banned(self):
        res = permission_manager.check_filesystem_access(
            r"C:\Windows\System32\test.dll",
            operation=FileOperation.DELETE
        )
        assert res.allowed is False
        assert "DENIED" in res.reason or "protected system directory" in res.reason

    def test_5_read_env_secret_banned(self):
        res = permission_manager.check_filesystem_access(
            r"C:\Users\Admin\Project-Falso\.env",
            operation=FileOperation.READ
        )
        assert res.allowed is False
        assert "strictly prohibited" in res.reason

    def test_6_run_pytest_in_project_falso_approved(self):
        res = permission_manager.check_command_execution(
            "pytest",
            args=["tests/test_backend/test_brain.py"],
            working_dir=r"C:\Users\Admin\Project-Falso"
        )
        assert res.allowed is True

    def test_7_run_arbitrary_powershell_denied(self):
        res = permission_manager.check_command_execution(
            "powershell_arbitrary_script",
            args=["Invoke-Expression", "Get-Process"]
        )
        assert res.allowed is False
        assert "not in controlled command registry" in res.reason

    def test_8_send_email_high_impact_requires_confirmation(self):
        res = permission_manager.check_capability("message.send", target="john@example.com")
        assert res.allowed is True
        assert res.requires_confirmation is True
        assert res.level == PermissionLevel.LEVEL_4_EXTERNAL_ACTION

    @pytest.mark.asyncio
    async def test_9_falso_lockdown_command(self):
        brain = BrainService(provider=FakePermProvider())
        events = [json.loads(line) async for line in brain.chat("FALSO lockdown")]
        full_text = "".join(e.get("response", "") for e in events)
        assert "Emergency Lockdown Activated" in full_text
        assert permission_manager.is_lockdown_active() is True

        # Verify filesystem access & tool executions are blocked during lockdown
        res = permission_manager.check_filesystem_access(r"C:\Users\Admin\Project-Falso\app\main.py", operation=FileOperation.WRITE)
        assert res.allowed is False
        assert "Lockdown Active" in res.reason

        # Re-enable lockdown for subsequent tests
        permission_manager.disable_lockdown()
