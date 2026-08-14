"""
FALSO 4.9 Application Skill Registry.

Registers and discovers all capability skills for the Adaptive Computer Operator.
"""

from __future__ import annotations

import logging
from typing import Any

from app.services.automation.android.skills import (
    AndroidApplicationSkill,
    AndroidCallingSkill,
    AndroidContactsSkill,
    AndroidDeviceSkill,
    AndroidMessagingSkill,
)
from app.services.automation.operator.skills.base_skill import BaseSkill
from app.services.automation.operator.skills.calculator_skill import CalculatorSkill
from app.services.automation.operator.skills.chrome_skill import ChromeSkill
from app.services.automation.operator.skills.cybersecurity_skill import CybersecuritySkill
from app.services.automation.operator.skills.explorer_skill import ExplorerSkill
from app.services.automation.operator.skills.notepad_skill import NotepadSkill
from app.services.automation.operator.skills.vscode_skill import VSCodeSkill

logger = logging.getLogger(__name__)


class SkillRegistry:
    """Central registry of application and system skills."""

    def __init__(self) -> None:
        self._skills: list[BaseSkill] = []
        self._register_default_skills()

    def _register_default_skills(self) -> None:
        self.register(CalculatorSkill())
        self.register(NotepadSkill())
        self.register(ChromeSkill())
        self.register(ExplorerSkill())
        self.register(VSCodeSkill())
        self.register(CybersecuritySkill())
        self.register(AndroidDeviceSkill())
        self.register(AndroidApplicationSkill())
        self.register(AndroidContactsSkill())
        self.register(AndroidCallingSkill())
        self.register(AndroidMessagingSkill())

    def register(self, skill: BaseSkill) -> None:
        self._skills.append(skill)
        logger.debug("[SKILL_REGISTRY] Registered skill: %s", skill.name)

    def find_skill(self, target: str, action: str) -> BaseSkill | None:
        """Find first skill capable of handling target and action."""
        for skill in self._skills:
            if skill.can_handle(target, action):
                return skill
        return None

    def list_skills(self) -> list[str]:
        return [s.name for s in self._skills]


skill_registry = SkillRegistry()
