"""
FALSO 4.9 Adaptive Computer Operator Module.
"""

from app.services.automation.operator.action_selector import ControlMethod, action_selector
from app.services.automation.operator.computer_observer import computer_observer
from app.services.automation.operator.computer_state import (
    BrowserStateInfo,
    ComputerState,
    EvidenceType,
    StateValue,
    UIElementInfo,
    VerifiedActionRecord,
    WindowInfo,
)
from app.services.automation.operator.operator_engine import operator_engine
from app.services.automation.operator.pronoun_resolver import pronoun_resolver
from app.services.automation.operator.skills.skill_registry import skill_registry

__all__ = [
    "BrowserStateInfo",
    "ComputerState",
    "ControlMethod",
    "EvidenceType",
    "StateValue",
    "UIElementInfo",
    "VerifiedActionRecord",
    "WindowInfo",
    "action_selector",
    "computer_observer",
    "operator_engine",
    "pronoun_resolver",
    "skill_registry",
]
