"""Permission service for FALSO Spatial OS.

Validates filesystem paths against allowed locations and manages
confirmation tokens for destructive or state-changing operations.
"""

import logging
import uuid
import time
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

USER_HOME = Path.home()
DEFAULT_ALLOWED_DIRECTORIES = [
    (USER_HOME / "Desktop").resolve(),
    (USER_HOME / "Documents").resolve(),
    (USER_HOME / "Downloads").resolve(),
    (USER_HOME / "Projects").resolve(),
    Path("c:/Users/Admin/Project-Falso").resolve()
]


from enum import Enum

class PermissionLevel(str, Enum):
    READ = "READ"
    WRITE = "WRITE"
    EXECUTE = "EXECUTE"
    ADMIN = "ADMIN"

ADMIN_ACTIONS = {
    "delete_file", "delete_folder", "run_terminal_command", "kill_process",
    "install_software", "modify_system_settings", "registry_change", "format_drive"
}
EXECUTE_ACTIONS = {"open_app", "close_app", "launch_website", "run_script"}
WRITE_ACTIONS = {"create_file", "create_folder", "rename_file", "copy_file", "move_file"}
READ_ACTIONS = {"read_file", "open_file", "search_files", "open_folder", "list_files"}


class PermissionService:
    """Manages permissions, audit logging, and action confirmation tokens."""

    def __init__(self):
        self.allowed_directories = [p for p in DEFAULT_ALLOWED_DIRECTORIES if p.exists()]
        # Token storage for pending actions: token -> {action, target_path, created_at, metadata}
        self.pending_tokens: Dict[str, Dict[str, Any]] = {}
        self.action_logs: list[Dict[str, Any]] = []

    def get_permission_level(self, action: str) -> PermissionLevel:
        action_lower = action.lower()
        if action_lower in ADMIN_ACTIONS:
            return PermissionLevel.ADMIN
        if action_lower in EXECUTE_ACTIONS:
            return PermissionLevel.EXECUTE
        if action_lower in WRITE_ACTIONS:
            return PermissionLevel.WRITE
        return PermissionLevel.READ

    def log_action(self, action: str, target: str, status: str, metadata: Optional[Dict[str, Any]] = None):
        level = self.get_permission_level(action)
        entry = {
            "timestamp": time.time(),
            "action": action,
            "level": level.value,
            "target": target,
            "status": status,
            "metadata": metadata or {}
        }
        self.action_logs.append(entry)
        logger.info("[SECURITY AUDIT] Action: %s | Level: %s | Target: %s | Status: %s", action, level.value, target, status)

    def is_path_allowed(self, target_path: str) -> bool:
        """Verifies if a given file/folder path is within an allowed directory."""
        try:
            resolved = Path(target_path).resolve()
            for allowed in self.allowed_directories:
                if resolved == allowed or allowed in resolved.parents:
                    return True
            return False
        except Exception as e:
            logger.warning(f"Error checking permission for path {target_path}: {e}")
            return False

    def create_confirmation_token(self, action: str, target_path: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """Generates a confirmation token for sensitive operations (delete, move, kill)."""
        token = str(uuid.uuid4())
        self.pending_tokens[token] = {
            "token": token,
            "action": action,
            "target_path": target_path,
            "metadata": metadata or {},
            "created_at": time.time()
        }
        self.log_action(action, target_path, "CONFIRMATION_REQUIRED", {"token": token})
        return token

    def confirm_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Validates and consumes a confirmation token."""
        self._cleanup_expired_tokens()
        if token in self.pending_tokens:
            return self.pending_tokens.pop(token)
        return None

    def _cleanup_expired_tokens(self, ttl_seconds: float = 300.0):
        """Removes tokens older than 5 minutes."""
        now = time.time()
        expired = [t for t, data in self.pending_tokens.items() if now - data["created_at"] > ttl_seconds]
        for t in expired:
            self.pending_tokens.pop(t, None)


# Global singleton instance
permission_service = PermissionService()
