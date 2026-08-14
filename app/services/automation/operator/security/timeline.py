"""
FALSO 4.11 Security Timeline.

Maintains a bounded ring buffer of non-sensitive security events:
- process started / stopped
- port opened / closed
- baseline updated / restored
- security finding detected
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
import time
from typing import Any

from app.services.automation.operator.security.evidence import SecretRedactor


@dataclass
class TimelineEvent:
    event_id: str
    event_type: str
    target: str
    details: dict[str, Any] = field(default_factory=dict)
    source: str = "security_observer"
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "target": self.target,
            "details": SecretRedactor.redact_dict(self.details),
            "source": self.source,
            "timestamp": self.timestamp,
        }


class SecurityTimeline:
    """Bounded history of security-relevant environmental events."""

    def __init__(self, max_events: int = 100) -> None:
        self._events: deque[TimelineEvent] = deque(maxlen=max_events)
        self._counter: int = 0

    def record_event(
        self,
        event_type: str,
        target: str,
        details: dict[str, Any] | None = None,
        source: str = "security_observer",
    ) -> TimelineEvent:
        self._counter += 1
        ev = TimelineEvent(
            event_id=f"evt_{self._counter}",
            event_type=event_type,
            target=target,
            details=details or {},
            source=source,
            timestamp=time.time(),
        )
        self._events.append(ev)
        return ev

    def get_recent_events(self, limit: int = 20) -> list[dict[str, Any]]:
        events = list(self._events)
        return [e.to_dict() for e in events[-limit:]]

    def get_events_before(self, timestamp: float, limit: int = 10) -> list[dict[str, Any]]:
        matching = [e.to_dict() for e in self._events if e.timestamp <= timestamp]
        return matching[-limit:]

    def clear(self) -> None:
        self._events.clear()


security_timeline = SecurityTimeline()
