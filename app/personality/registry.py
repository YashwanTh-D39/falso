from __future__ import annotations

import logging
from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    from app.personality.base import Personality

logger = logging.getLogger(__name__)


class PersonalityRegistry:
    _personalities: ClassVar[dict[str, type[Personality]]] = {}

    @classmethod
    def register(cls, personality_cls: type[Personality]) -> type[Personality]:
        pid = personality_cls.id
        if not pid:
            pid = personality_cls.__name__.lower()
            personality_cls.id = pid

        if pid in cls._personalities:
            logger.warning("Personality '%s' already registered — overwriting", pid)

        cls._personalities[pid] = personality_cls
        logger.info("Registered personality '%s': %s", pid, personality_cls.__name__)
        return personality_cls

    @classmethod
    def get(cls, pid: str) -> type[Personality] | None:
        return cls._personalities.get(pid)

    @classmethod
    def list(cls) -> list[dict[str, str]]:
        return [
            {"id": p.id, "name": p.name, "description": p.description}
            for p in cls._personalities.values()
        ]


def register_personality(cls: type[Personality]) -> type[Personality]:
    return PersonalityRegistry.register(cls)