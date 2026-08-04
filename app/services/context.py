from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

_PENDING_TTL: float = 300.0  # 5 minutes


@dataclass
class PendingAction:
    tool: str
    intent: str
    args: dict[str, Any]
    timestamp: float
    confirmation_required: bool = False

    @property
    def expired(self) -> bool:
        return (time.monotonic() - self.timestamp) > _PENDING_TTL


@dataclass
class ConversationContext:
    pending: PendingAction | None = None
    last_filename: str | None = None

    def store_pending(
        self,
        tool: str,
        intent: str,
        args: dict[str, Any],
        confirmation_required: bool = False,
    ) -> None:
        self.pending = PendingAction(
            tool=tool,
            intent=intent,
            args=args,
            timestamp=time.monotonic(),
            confirmation_required=confirmation_required,
        )

    def clear_pending(self) -> None:
        self.pending = None

    @property
    def has_pending(self) -> bool:
        return self.pending is not None and not self.pending.expired
