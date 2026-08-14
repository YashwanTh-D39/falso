from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, ClassVar

if TYPE_CHECKING:
    from app.tools.base import Tool

logger = logging.getLogger(__name__)


class ToolRegistry:
    _tools: ClassVar[dict[str, type[Tool]]] = {}

    @classmethod
    def register(cls, tool_cls: type[Tool]) -> type[Tool]:
        name = tool_cls.name
        if not name:
            name = tool_cls.__name__.lower()
            tool_cls.name = name

        if name in cls._tools:
            logger.warning("Tool '%s' already registered — overwriting", name)

        cls._tools[name] = tool_cls
        logger.info("Registered tool '%s': %s", name, tool_cls.__name__)
        return tool_cls

    @classmethod
    def get(cls, name: str) -> type[Tool] | None:
        return cls._tools.get(name)

    @classmethod
    def list(cls) -> list[dict[str, Any]]:
        return [
            {
                "name": t.name,
                "description": t.description,
                "parameters": t.parameters,
                "output_schema": getattr(t, "output_schema", {}),
                "permission_level": getattr(t, "permission_level", "read_only"),
                "timeout": getattr(t, "timeout", 5.0),
            }
            for t in cls._tools.values()
        ]
