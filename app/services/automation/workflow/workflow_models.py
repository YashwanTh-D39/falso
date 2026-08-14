"""
Data Models for FALSO Multi-Step Web Workflow Engine (FALSO 4.8).

Defines WorkflowState, WorkflowStepState, WorkflowStep, BrowserContextState, and WorkflowResult.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import time
from typing import Any, Dict, List, Optional


class WorkflowStepState(str, Enum):
    PENDING = "PENDING"
    EXECUTING = "EXECUTING"
    VERIFYING = "VERIFYING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    SKIPPED = "SKIPPED"


class WorkflowState(str, Enum):
    PLANNING = "PLANNING"
    WAITING_PERMISSION = "WAITING_PERMISSION"
    EXECUTING = "EXECUTING"
    VERIFYING = "VERIFYING"
    RECOVERING = "RECOVERING"
    WAITING_USER = "WAITING_USER"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


@dataclass
class WorkflowStep:
    workflow_id: str = ""
    step_id: int = 1
    action_id: str = ""
    action: str = ""
    target: str = ""
    params: Dict[str, Any] = field(default_factory=dict)
    status: WorkflowStepState = WorkflowStepState.PENDING
    before_state: Dict[str, Any] = field(default_factory=dict)
    after_state: Dict[str, Any] = field(default_factory=dict)
    verification: str = ""
    attempt_count: int = 0
    duration_ms: float = 0.0
    capability: str = "browser.interact"
    description: str = ""
    requires_confirmation: bool = False
    dependencies: List[int] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "step_id": self.step_id,
            "action_id": self.action_id,
            "action": self.action,
            "target": self.target,
            "status": self.status.value,
            "verification": self.verification,
            "attempt_count": self.attempt_count,
            "duration_ms": self.duration_ms,
            "requires_confirmation": self.requires_confirmation,
        }


@dataclass
class BrowserContextState:
    active_browser: str = "Chrome"
    active_window: str = "Chrome"
    current_url: str = "about:blank"
    page_title: str = ""
    active_tab: int = 1
    known_tabs: List[Dict[str, str]] = field(default_factory=list)
    last_observation_timestamp: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "active_browser": self.active_browser,
            "current_url": self.current_url,
            "page_title": self.page_title,
            "active_tab": self.active_tab,
            "known_tabs_count": len(self.known_tabs),
        }


@dataclass
class WorkflowResult:
    workflow_id: str
    session_id: str
    originating_request_id: str
    goal: str
    state: WorkflowState
    steps: List[WorkflowStep]
    final_message: str
    browser_context: BrowserContextState
    duration_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "session_id": self.session_id,
            "originating_request_id": self.originating_request_id,
            "goal": self.goal,
            "state": self.state.value,
            "steps": [s.to_dict() for s in self.steps],
            "final_message": self.final_message,
            "duration_ms": self.duration_ms,
        }
