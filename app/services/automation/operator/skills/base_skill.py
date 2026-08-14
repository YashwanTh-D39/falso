"""
FALSO 4.9 Base Application Skill.

All application skills inherit from BaseSkill, sharing:
- Permission checking (PermissionManager)
- Computer observation (ComputerObserver)
- Action selector integration
- Truthful state verification
- Security audit logging
- Physical input delegation (Win32 / UIA / Browser)
"""

from __future__ import annotations

import abc
import logging
from typing import Any

from app.services.automation.operator.computer_observer import computer_observer
from app.services.automation.operator.computer_state import ComputerState, VerifiedActionRecord
from app.services.automation.permissions import PermissionLevel, RiskLevel, permission_manager
from app.services.automation.windows.executor import windows_executor

logger = logging.getLogger(__name__)


class BaseSkill(abc.ABC):
    """Abstract base class for all FALSO application and system skills."""

    name: str = "base"
    allowed_applications: list[str] = []
    default_risk_level: RiskLevel = RiskLevel.LOW

    def __init__(self) -> None:
        self.observer = computer_observer
        self.executor = windows_executor

    @abc.abstractmethod
    def can_handle(self, target: str, action: str) -> bool:
        """Return True if this skill is capable of handling the target & action."""
        raise NotImplementedError

    @abc.abstractmethod
    def execute(self, action: str, target: str, params: dict[str, Any], state: ComputerState) -> dict[str, Any]:
        """Execute physical action against target application and return result dictionary."""
        raise NotImplementedError

    @abc.abstractmethod
    def verify(self, action: str, target: str, before_state: ComputerState, after_state: ComputerState, result: dict[str, Any]) -> tuple[bool, str]:
        """Authoritatively verify that the intended action succeeded against real Windows state."""
        raise NotImplementedError

    def check_permission(self, target: str, action: str, params: dict[str, Any]) -> tuple[bool, str, RiskLevel]:
        """Validate permission and scope with PermissionManager."""
        risk = permission_manager.get_risk_level(action, target, params)
        perm = permission_manager.check_capability(f"windows.{action}", target=target)
        return perm.allowed, perm.reason, risk
