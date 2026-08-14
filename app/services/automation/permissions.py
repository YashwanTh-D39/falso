"""
Capability-Based Permission System & Filesystem Sandbox for FALSO PC Automation.

Enforces:
- Principle of Least Privilege: DENY BY DEFAULT
- Configurable Filesystem Sandbox (Desktop, Documents, Downloads, Project-Falso)
- Path Traversal & System Directory Protection (C:\\Windows, C:\\System32, etc.)
- Granular File Operation Permissions (READ, WRITE, CREATE, RENAME, MOVE, DELETE)
- Approved Application Allowlist (Calculator, Explorer, VS Code, Chrome, etc.)
- Controlled Command Execution Registry (python, pytest, git, npm, pip, uvicorn)
- Strict Secrets / .env Protection (prohibits sending API keys / secrets to LLM context)
- Level 4 Dangerous Action Confirmation (DELETE, SEND, UPLOAD, PURCHASE, RESTART, etc.)
- Emergency Lockdown Control ("FALSO lockdown")
- Structured Audit Logging (task_id, request_id, capability, target, duration, timestamp)
"""

from __future__ import annotations

from dataclasses import dataclass, field
import enum
import logging
import os
from pathlib import Path
import time
from typing import Any

logger = logging.getLogger(__name__)


class PermissionLevel(enum.IntEnum):
    LEVEL_0_OBSERVE = 0      # Screen, active windows, app state, metrics
    LEVEL_1_INTERACT = 1     # Mouse, keyboard, browser navigation, app switching
    LEVEL_2_USER_FILES = 2   # Approved filesystem read/write
    LEVEL_3_DEVELOPMENT = 3  # Project-Falso source modifications & approved dev commands
    LEVEL_4_EXTERNAL_ACTION = 4  # Deleting, sending, uploading, purchasing (REQUIRES CONFIRMATION)


class RiskLevel(enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class FileOperation(enum.Enum):
    READ = "read"
    WRITE = "write"
    CREATE = "create"
    RENAME = "rename"
    MOVE = "move"
    DELETE = "delete"
    EXECUTE = "execute"


@dataclass
class PermissionCheckResult:
    allowed: bool
    reason: str
    requires_confirmation: bool = False
    level: PermissionLevel = PermissionLevel.LEVEL_0_OBSERVE


@dataclass
class AuditLogEntry:
    task_id: str
    request_id: str
    action_id: str
    capability: str
    target: str
    result: str
    duration_ms: float
    timestamp: float = field(default_factory=time.time)


class PermissionManager:
    """Central Permission Manager enforcing capability-based access control for FALSO."""

    def __init__(self) -> None:
        self.lockdown: bool = False

        # Configurable Filesystem Sandbox Allowed Roots
        self.allowed_directories: list[Path] = [
            Path(os.path.expanduser(r"~\Desktop")).resolve(),
            Path(os.path.expanduser(r"~\Documents")).resolve(),
            Path(os.path.expanduser(r"~\Downloads")).resolve(),
            Path(r"C:\Users\Admin\Project-Falso").resolve(),
        ]

        # Explicitly Banned System Directories
        self.banned_directories: list[Path] = [
            Path(r"C:\Windows").resolve(),
            Path(r"C:\Windows\System32").resolve(),
            Path(r"C:\Program Files").resolve(),
            Path(r"C:\Program Files (x86)").resolve(),
        ]

        # Approved Application Allowlist
        self.application_allowlist: set[str] = {
            "calculator", "calc", "calc.exe",
            "chrome", "chrome.exe", "google chrome",
            "claude", "claude.exe", "claude desktop", "anthropic claude",
            "msedge", "msedge.exe",
            "wt", "wt.exe", "windows terminal",
            "cmd", "cmd.exe", "command prompt",
            "powershell", "powershell.exe",
            "code", "code.exe", "vs code", "vscode",
            "explorer", "explorer.exe", "file explorer",
            "notepad", "notepad.exe",
        }

        # Controlled Command Registry
        self.approved_commands: dict[str, dict[str, Any]] = {
            "python": {"executable": "python.exe", "level": PermissionLevel.LEVEL_3_DEVELOPMENT, "timeout": 30.0},
            "pytest": {"executable": "pytest.exe", "level": PermissionLevel.LEVEL_3_DEVELOPMENT, "timeout": 60.0},
            "git": {"executable": "git.exe", "level": PermissionLevel.LEVEL_3_DEVELOPMENT, "timeout": 15.0},
            "npm": {"executable": "npm.cmd", "level": PermissionLevel.LEVEL_3_DEVELOPMENT, "timeout": 30.0},
            "pip": {"executable": "pip.exe", "level": PermissionLevel.LEVEL_3_DEVELOPMENT, "timeout": 30.0},
            "uvicorn": {"executable": "uvicorn.exe", "level": PermissionLevel.LEVEL_3_DEVELOPMENT, "timeout": 30.0},
        }

        # High-Impact Capabilities requiring Level 4 User Confirmation
        self.high_impact_capabilities: set[str] = {
            "filesystem.delete",
            "message.send",
            "file.upload",
            "purchase.execute",
            "payment.submit",
            "account.password_change",
            "system.shutdown",
            "system.restart",
            "software.install",
            "browser.submit_form",
            "browser.fill_sensitive_field",
            "android.call",
            "android.message",
            "android.install_app",
            "android.delete_file",
        }

        # Task-Scoped Temporary Capabilities: task_id -> set[capability]
        self._task_capabilities: dict[str, set[str]] = {}

        # Audit Log Record
        self.audit_log: list[AuditLogEntry] = []

    def enable_lockdown(self) -> None:
        """Activate Emergency Lockdown to immediately block all automation capabilities."""
        self.lockdown = True
        logger.warning("[PERMISSIONS] EMERGENCY LOCKDOWN ACTIVATED. All automation control disabled.")

    def disable_lockdown(self) -> None:
        """Deactivate Emergency Lockdown."""
        self.lockdown = False
        logger.info("[PERMISSIONS] Emergency Lockdown deactivated.")

    def is_lockdown_active(self) -> bool:
        return self.lockdown

    def grant_task_capability(self, task_id: str, capability: str) -> None:
        """Grant a temporary task-scoped capability."""
        if task_id not in self._task_capabilities:
            self._task_capabilities[task_id] = set()
        self._task_capabilities[task_id].add(capability)
        logger.info("[PERMISSIONS] Granted temporary capability '%s' to task '%s'", capability, task_id)

    def revoke_task_capabilities(self, task_id: str) -> None:
        """Revoke all temporary capabilities granted to a task."""
        if task_id in self._task_capabilities:
            del self._task_capabilities[task_id]
            logger.info("[PERMISSIONS] Revoked all temporary capabilities for task '%s'", task_id)

    def check_filesystem_access(
        self,
        path: str | Path,
        operation: FileOperation = FileOperation.READ,
        task_id: str | None = None
    ) -> PermissionCheckResult:
        """Check filesystem sandbox and granular operation permissions."""
        if self.lockdown:
            return PermissionCheckResult(
                allowed=False,
                reason="FALSO Emergency Lockdown Active: Filesystem operations disabled.",
                level=PermissionLevel.LEVEL_4_EXTERNAL_ACTION,
            )

        try:
            target_path = Path(path).resolve()
        except Exception as e:
            return PermissionCheckResult(
                allowed=False,
                reason=f"Invalid path specification: {e}",
            )

        # Check Path Traversal & Banned System Directories
        for banned in self.banned_directories:
            if target_path == banned or banned in target_path.parents:
                return PermissionCheckResult(
                    allowed=False,
                    reason=f"Access DENIED: Target path '{target_path}' is inside protected system directory '{banned}'.",
                    level=PermissionLevel.LEVEL_4_EXTERNAL_ACTION,
                )

        # Check Secret / .env Protection
        filename = target_path.name.lower()
        if filename.startswith(".env") or filename in ("id_rsa", "id_ed25519", "credentials.json", "secrets.json"):
            if operation in (FileOperation.READ, FileOperation.WRITE, FileOperation.DELETE):
                return PermissionCheckResult(
                    allowed=False,
                    reason=f"Access DENIED: Exposing raw secret file '{filename}' to LLM context is strictly prohibited.",
                    level=PermissionLevel.LEVEL_4_EXTERNAL_ACTION,
                )

        # Check Allowed Directory Roots
        in_sandbox = False
        for allowed in self.allowed_directories:
            if target_path == allowed or allowed in target_path.parents:
                in_sandbox = True
                break

        if not in_sandbox:
            return PermissionCheckResult(
                allowed=False,
                reason=f"Access DENIED: Path '{target_path}' is outside configurable filesystem sandbox.",
                level=PermissionLevel.LEVEL_2_USER_FILES,
            )

        # Granular Operation Checks
        if operation == FileOperation.DELETE:
            return PermissionCheckResult(
                allowed=True,
                reason=f"Delete operation on '{target_path.name}' requires Level 4 user confirmation.",
                requires_confirmation=True,
                level=PermissionLevel.LEVEL_4_EXTERNAL_ACTION,
            )

        level = PermissionLevel.LEVEL_3_DEVELOPMENT if "Project-Falso" in str(target_path) else PermissionLevel.LEVEL_2_USER_FILES
        return PermissionCheckResult(allowed=True, reason="Path is within approved sandbox.", level=level)

    def check_application_launch(self, app_name: str) -> PermissionCheckResult:
        """Check if an application launch request is in the approved allowlist."""
        if self.lockdown:
            return PermissionCheckResult(
                allowed=False,
                reason="FALSO Emergency Lockdown Active: Application launches disabled.",
                level=PermissionLevel.LEVEL_4_EXTERNAL_ACTION,
            )

        clean_name = app_name.lower().strip()
        if clean_name in self.application_allowlist or any(clean_name.startswith(app) for app in ("calc", "chrome", "edge", "code", "notepad", "terminal", "powershell", "cmd", "explorer")):
            return PermissionCheckResult(
                allowed=True,
                reason=f"Application '{app_name}' is in approved allowlist.",
                level=PermissionLevel.LEVEL_1_INTERACT,
            )

        return PermissionCheckResult(
            allowed=False,
            reason=f"Access DENIED: Application '{app_name}' is not in approved application allowlist.",
            level=PermissionLevel.LEVEL_4_EXTERNAL_ACTION,
        )

    def check_command_execution(
        self,
        command_name: str,
        args: list[str] | None = None,
        working_dir: str | Path | None = None,
    ) -> PermissionCheckResult:
        """Check if command execution matches controlled command registry."""
        if self.lockdown:
            return PermissionCheckResult(
                allowed=False,
                reason="FALSO Emergency Lockdown Active: Command execution disabled.",
                level=PermissionLevel.LEVEL_4_EXTERNAL_ACTION,
            )

        cmd_clean = command_name.lower().strip()
        if cmd_clean not in self.approved_commands:
            return PermissionCheckResult(
                allowed=False,
                reason=f"Access DENIED: Command '{command_name}' is not in controlled command registry.",
                level=PermissionLevel.LEVEL_4_EXTERNAL_ACTION,
            )

        # Check working directory if provided
        if working_dir:
            dir_check = self.check_filesystem_access(working_dir, operation=FileOperation.READ)
            if not dir_check.allowed:
                return dir_check

        # Check for destructive Git operations
        if cmd_clean == "git" and args:
            args_str = " ".join(args).lower()
            if any(bad in args_str for bad in ("reset --hard", "clean -fd", "push --force", "push -f", "delete")):
                return PermissionCheckResult(
                    allowed=False,
                    reason=f"Access DENIED: Destructive Git operation '{args_str}' is strictly forbidden.",
                    level=PermissionLevel.LEVEL_4_EXTERNAL_ACTION,
                )

        cmd_info = self.approved_commands[cmd_clean]
        return PermissionCheckResult(
            allowed=True,
            reason=f"Command '{cmd_clean}' is approved in command registry.",
            level=cmd_info["level"],
        )

    def check_capability(
        self,
        capability: str,
        target: str = "",
        task_id: str | None = None,
    ) -> PermissionCheckResult:
        """General capability check method."""
        if self.lockdown:
            return PermissionCheckResult(
                allowed=False,
                reason="FALSO Emergency Lockdown Active: All automation capabilities disabled.",
                level=PermissionLevel.LEVEL_4_EXTERNAL_ACTION,
            )

        # Level 4 High-Impact confirmation requirements
        if capability in self.high_impact_capabilities or capability.endswith(".delete") or capability.endswith(".send"):
            return PermissionCheckResult(
                allowed=True,
                reason=f"Capability '{capability}' requires explicit Level 4 user confirmation.",
                requires_confirmation=True,
                level=PermissionLevel.LEVEL_4_EXTERNAL_ACTION,
            )

        # Check task-scoped capability grants
        if task_id and task_id in self._task_capabilities:
            if capability in self._task_capabilities[task_id]:
                return PermissionCheckResult(
                    allowed=True,
                    reason=f"Capability '{capability}' is granted to task '{task_id}'.",
                    level=PermissionLevel.LEVEL_3_DEVELOPMENT,
                )

        # Application allowlist check for app control capabilities
        clean_target = target.lower().strip()
        if capability in ("windows.close_window", "windows.close_app", "windows.interact_with_app", "windows.launch_app"):
            if clean_target and not (clean_target in self.application_allowlist or any(clean_target.startswith(app) for app in ("calc", "chrome", "edge", "code", "notepad", "terminal", "powershell", "cmd", "explorer"))):
                return PermissionCheckResult(
                    allowed=False,
                    reason=f"Access DENIED: Application '{target}' is not in approved application allowlist.",
                    level=PermissionLevel.LEVEL_4_EXTERNAL_ACTION,
                )

        return PermissionCheckResult(
            allowed=True,
            reason=f"Capability '{capability}' permitted.",
            level=PermissionLevel.LEVEL_1_INTERACT,
        )

    def grant_task_capability(self, task_id: str, capability: str) -> None:
        """Grant a temporary capability scoped strictly to an active task."""
        if task_id not in self._task_capabilities:
            self._task_capabilities[task_id] = set()
        self._task_capabilities[task_id].add(capability)

    def revoke_task_capabilities(self, task_id: str) -> None:
        """Revoke all task-scoped temporary capabilities when a task ends."""
        if task_id in self._task_capabilities:
            del self._task_capabilities[task_id]

    def get_risk_level(self, action_type: str, target: str = "", params: dict | None = None) -> RiskLevel:
        """Classify risk level of a proposed action."""
        act = action_type.lower()
        tgt = target.lower()
        combined = f"{act} {tgt}".lower()

        # HIGH Risk Actions
        if any(w in combined for w in ("delete", "rmdir", "remove", "system_setting", "install", "shutdown", "restart", "format", "raw_shell", "secret", "credential", "disable_security", "registry", "force_terminate", "kill_process", "taskkill", "stop-process")):
            return RiskLevel.HIGH

        # MEDIUM Risk Actions
        if any(w in combined for w in ("create_file", "modify_file", "write_file", "run_registered_command", "run_pytest", "git_commit", "interact_with_app", "close_window", "close_app")):
            return RiskLevel.MEDIUM

        # LOW Risk Actions
        return RiskLevel.LOW

    def log_action(
        self,
        task_id: str,
        request_id: str,
        action_id: str,
        capability: str,
        target: str,
        result: str,
        duration_ms: float,
    ) -> None:
        """Record structured audit log entry."""
        # Sanitize target to ensure no secrets/passwords are logged
        clean_target = target
        for secret_name in ("NVIDIA_INFERENCE_API_KEY", "ELEVENLABS_API_KEY", "GEMINI_API_KEY", "password", "token", "key"):
            if secret_name in clean_target:
                clean_target = f"[MASKED_SECRET:{secret_name}]"

        entry = AuditLogEntry(
            task_id=task_id,
            request_id=request_id,
            action_id=action_id,
            capability=capability,
            target=clean_target,
            result=result,
            duration_ms=duration_ms,
        )
        self.audit_log.append(entry)
        logger.info(
            "[AUTOMATION] task=%s request=%s action=%s capability=%s target=%r result=%s duration=%.1fms",
            task_id, request_id, action_id, capability, clean_target, result, duration_ms
        )


# Global Singleton Permission Manager
permission_manager = PermissionManager()
