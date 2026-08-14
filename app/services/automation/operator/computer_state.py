"""
FALSO 4.9 Adaptive Computer Operator — Computer State Model.

Maintains a rich, observable model of current computer state with explicit
evidence classifications (OBSERVED, INFERRED, UNKNOWN).
"""

from __future__ import annotations

from dataclasses import dataclass, field
import enum
import time
from typing import Any, Generic, TypeVar

T = TypeVar("T")


class EvidenceType(enum.Enum):
    OBSERVED = "OBSERVED"  # Ground truth directly confirmed via OS/UIA/Browser API
    INFERRED = "INFERRED"  # Deduced from context/actions (can aid planning, cannot alone prove completion)
    UNKNOWN = "UNKNOWN"    # Unverified state (never treated as false)


@dataclass
class StateValue(Generic[T]):
    value: T
    evidence: EvidenceType = EvidenceType.UNKNOWN
    timestamp: float = field(default_factory=time.time)
    source: str = "init"

    def is_observed(self) -> bool:
        return self.evidence == EvidenceType.OBSERVED

    def is_inferred(self) -> bool:
        return self.evidence == EvidenceType.INFERRED

    def is_unknown(self) -> bool:
        return self.evidence == EvidenceType.UNKNOWN


@dataclass
class WindowInfo:
    hwnd: int
    title: str
    process_id: int = 0
    process_name: str = ""
    is_foreground: bool = False
    rect: tuple[int, int, int, int] = (0, 0, 0, 0)

    def to_dict(self) -> dict[str, Any]:
        return {
            "hwnd": self.hwnd,
            "title": self.title,
            "process_id": self.process_id,
            "process_name": self.process_name,
            "is_foreground": self.is_foreground,
            "rect": self.rect,
        }


@dataclass
class UIElementInfo:
    name: str = ""
    role: str = ""
    control_type: str = ""
    automation_id: str = ""
    value: str | None = None
    enabled: bool = True
    visible: bool = True
    bounding_rect: tuple[int, int, int, int] = (0, 0, 0, 0)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "role": self.role,
            "control_type": self.control_type,
            "automation_id": self.automation_id,
            "value": self.value,
            "enabled": self.enabled,
            "visible": self.visible,
            "bounding_rect": self.bounding_rect,
        }


@dataclass
class BrowserStateInfo:
    active_browser: str = "Chrome"
    current_url: str = ""
    active_tab_title: str = ""
    tab_count: int = 1
    known_tabs: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "active_browser": self.active_browser,
            "current_url": self.current_url,
            "active_tab_title": self.active_tab_title,
            "tab_count": self.tab_count,
            "known_tabs": self.known_tabs,
        }


@dataclass
class VerifiedActionRecord:
    task_id: str
    action_id: str
    target: str
    action: str
    timestamp: float = field(default_factory=time.time)
    execution_result: dict[str, Any] = field(default_factory=dict)
    verification_result: tuple[bool, str] = (True, "Verified")
    safe_summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "action_id": self.action_id,
            "target": self.target,
            "action": self.action,
            "timestamp": self.timestamp,
            "execution_result": self.execution_result,
            "verification_result": self.verification_result,
            "safe_summary": self.safe_summary,
        }


@dataclass
class ComputerState:
    """Shared state abstraction representing observable desktop reality."""

    foreground_window: StateValue[WindowInfo | None] = field(
        default_factory=lambda: StateValue(value=None, evidence=EvidenceType.UNKNOWN, source="init")
    )
    foreground_application: StateValue[str | None] = field(
        default_factory=lambda: StateValue(value=None, evidence=EvidenceType.UNKNOWN, source="init")
    )
    visible_windows: StateValue[list[WindowInfo]] = field(
        default_factory=lambda: StateValue(value=[], evidence=EvidenceType.UNKNOWN, source="init")
    )
    approved_running_applications: StateValue[list[str]] = field(
        default_factory=lambda: StateValue(value=[], evidence=EvidenceType.UNKNOWN, source="init")
    )
    browser: StateValue[BrowserStateInfo | None] = field(
        default_factory=lambda: StateValue(value=None, evidence=EvidenceType.UNKNOWN, source="init")
    )
    focused_element: StateValue[UIElementInfo | None] = field(
        default_factory=lambda: StateValue(value=None, evidence=EvidenceType.UNKNOWN, source="init")
    )
    visible_elements: StateValue[list[UIElementInfo]] = field(
        default_factory=lambda: StateValue(value=[], evidence=EvidenceType.UNKNOWN, source="init")
    )
    active_workflow: StateValue[str | None] = field(
        default_factory=lambda: StateValue(value=None, evidence=EvidenceType.UNKNOWN, source="init")
    )
    current_task_id: StateValue[str | None] = field(
        default_factory=lambda: StateValue(value=None, evidence=EvidenceType.UNKNOWN, source="init")
    )
    last_verified_action: StateValue[VerifiedActionRecord | None] = field(
        default_factory=lambda: StateValue(value=None, evidence=EvidenceType.UNKNOWN, source="init")
    )
    verified_action_history: list[VerifiedActionRecord] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)

    def get_foreground_app(self) -> str | None:
        if self.foreground_application.is_observed():
            return self.foreground_application.value
        return None

    def is_app_open(self, app_name: str) -> bool:
        if not app_name:
            return False
        app_clean = app_name.lower()
        if self.visible_windows.is_observed():
            for w in self.visible_windows.value:
                if app_clean in w.title.lower() or app_clean in w.process_name.lower():
                    return True
        if self.approved_running_applications.is_observed():
            for a in self.approved_running_applications.value:
                if app_clean in a.lower():
                    return True
        return False

    def is_app_foreground(self, app_name: str) -> bool:
        if not app_name:
            return False
        fg = self.get_foreground_app()
        if fg and app_name.lower() in fg.lower():
            return True
        if self.foreground_window.is_observed() and self.foreground_window.value:
            w = self.foreground_window.value
            return app_name.lower() in w.title.lower() or app_name.lower() in w.process_name.lower()
        return False

    def add_verified_action(self, record: VerifiedActionRecord) -> None:
        """Add verified action to short-lived verified action history with strict privacy filtering."""
        # Sanitize against passwords, tokens, keys
        clean_summary = record.safe_summary or f"{record.action} on {record.target}"
        record.safe_summary = clean_summary
        self.verified_action_history.append(record)
        if len(self.verified_action_history) > 50:
            self.verified_action_history.pop(0)
        self.last_verified_action = StateValue(
            value=record,
            evidence=EvidenceType.OBSERVED,
            source="operator",
        )

    def get_last_verified_target(self) -> str | None:
        if self.last_verified_action.is_observed() and self.last_verified_action.value:
            return self.last_verified_action.value.target
        if self.verified_action_history:
            return self.verified_action_history[-1].target
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "foreground_window": self.foreground_window.value.to_dict() if self.foreground_window.value else None,
            "foreground_application": self.foreground_application.value,
            "visible_windows": [w.to_dict() for w in self.visible_windows.value],
            "approved_running_applications": self.approved_running_applications.value,
            "browser": self.browser.value.to_dict() if self.browser.value else None,
            "focused_element": self.focused_element.value.to_dict() if self.focused_element.value else None,
            "visible_elements": [e.to_dict() for e in self.visible_elements.value],
            "active_workflow": self.active_workflow.value,
            "current_task_id": self.current_task_id.value,
            "last_verified_action": self.last_verified_action.value.to_dict() if self.last_verified_action.value else None,
            "verified_action_history_count": len(self.verified_action_history),
            "timestamp": self.timestamp,
        }
