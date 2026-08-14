from __future__ import annotations

from enum import Enum
import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, ClassVar

if TYPE_CHECKING:
    from app.services.context import ConversationContext

logger = logging.getLogger(__name__)


class PermissionLevel(str, Enum):
    READ_ONLY = "read_only"
    LOW_RISK = "low_risk"
    DESTRUCTIVE = "destructive"


@dataclass
class ToolResult:
    success: bool
    data: Any = None
    error: str | None = None
    execution_time: float | None = None


class Tool(ABC):
    name: str = ""
    description: str = ""
    parameters: ClassVar[dict] = {}
    output_schema: ClassVar[dict] = {}
    permission_level: ClassVar[PermissionLevel] = PermissionLevel.READ_ONLY
    timeout: float = 5.0

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        if not cls.name:
            cls.name = cls.__name__.lower()

    @classmethod
    def match_prompt(cls, prompt: str, context: ConversationContext | None = None) -> dict | None:
        prompt_lower = prompt.lower()

        if not re.search(r'\b' + re.escape(cls.name.lower()) + r'\b', prompt_lower):
            desc_lower = cls.description.lower()
            tokens = re.findall(r'[a-z]+', desc_lower)
            stop_words = {
                'the','a','an','is','are','was','were','be','been','have','has',
                'had','do','does','did','will','would','could','should','may',
                'might','can','shall','to','of','in','for','on','with','at','by',
                'from','as','into','through','and','but','or','if','while','that',
                'this','these','those','it','its','also','not','no','nor','only',
                'very','just','then','once','here','there','when','where','why',
                'how','all','each','every','both','few','more','most','other',
                'some','such','same','so','than','too','returns',
            }
            keywords = {t for t in tokens if t not in stop_words and len(t) > 2}
            if not any(re.search(r'\b' + re.escape(kw) + r'\b', prompt_lower) for kw in keywords):
                return None

        return {}

    @classmethod
    def format_result(cls, result: ToolResult) -> str:
        if not result.success:
            return f"Error: {result.error}"
        if isinstance(result.data, dict):
            lines = []
            for k, v in result.data.items():
                if v is None:
                    continue
                if isinstance(v, dict):
                    for sk, sv in v.items():
                        lines.append(f"{sk.title()}: {sv}")
                elif isinstance(v, list):
                    if k == "items":
                        for item in v:
                            t = item.get("type", "")
                            name = item.get("name", "")
                            size = item.get("size")
                            suffix = f" ({size} bytes)" if size is not None else ""
                            lines.append(f"  {t}: {name}{suffix}")
                    elif k == "matches":
                        lines.append(f"Matches ({len(v)}):")
                        for item in v:
                            lines.append(f"  {item.get('path', '')}")
                    else:
                        lines.append(f"{' '.join(w.capitalize() for w in k.split('_'))}:")
                        for item in v:
                            lines.append(f"  {item}")
                else:
                    label = " ".join(w.capitalize() for w in k.split("_"))
                    lines.append(f"{label}: {v}")
            return "\n".join(lines)
        return str(result.data)

    @abstractmethod
    async def execute(self, **kwargs: Any) -> ToolResult:
        ...
