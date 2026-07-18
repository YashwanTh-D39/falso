from __future__ import annotations

import json
import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.context import ConversationContext

logger = logging.getLogger(__name__)


@dataclass
class ToolResult:
    success: bool
    data: Any = None
    error: str | None = None
    execution_time: float | None = None


class Tool(ABC):
    name: str = ""
    description: str = ""
    parameters: dict = field(default_factory=dict)

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        if not cls.name:
            cls.name = cls.__name__.lower()

    @classmethod
    def match_prompt(cls, prompt: str, context: ConversationContext | None = None) -> dict | None:
        prompt_lower = prompt.lower()

        if re.search(r'\b' + re.escape(cls.name.lower()) + r'\b', prompt_lower):
            pass
        else:
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

        kwargs: dict = {}
        params = cls.parameters or {}
        props = params.get("properties", {})
        if not props:
            return kwargs

        if "command" in props:
            enum_vals = props["command"].get("enum", [])
            aliases = {"create": "write", "make": "write", "new": "write"}
            for word in re.findall(r'[a-zA-Z]+', prompt):
                w = word.lower()
                if w in aliases:
                    kwargs["command"] = aliases[w]
                    break
                if w in enum_vals:
                    kwargs["command"] = w
                    break
            if "command" not in kwargs:
                for cmd in enum_vals:
                    if cmd in prompt_lower:
                        kwargs["command"] = cmd
                        break

        if "path" in props and "command" in kwargs:
            cmd = kwargs["command"]
            rev = {v: k for k, v in {"create": "write", "make": "write", "new": "write"}.items() if v == cmd}
            triggers = {cmd} | set(rev.keys())
            words = prompt.split()
            for i, w in enumerate(words):
                if w.lower().strip(".,!?;:'\"") in triggers:
                    for j in range(i + 1, len(words)):
                        candidate = words[j].strip(".,!?;:'\"")
                        if candidate:
                            kwargs["path"] = candidate
                            break
                    break

        if "content" in props and "command" in kwargs and kwargs["command"] == "write" and "content" not in kwargs:
            kwargs["content"] = ""

        return kwargs

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
