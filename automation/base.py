from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass
class JobResult:
    job_id: str
    success: bool
    output: Any = None
    error: str | None = None
    executed_at: str = field(
        default_factory=lambda: datetime.now(UTC).isoformat()
    )


@dataclass
class AutomationJob:
    name: str
    action: Callable[..., Awaitable[Any]] | str
    interval_seconds: float
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    kwargs: dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    last_run: str | None = None
    run_count: int = 0
    max_runs: int | None = None  # None = run indefinitely
