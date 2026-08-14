"""
FALSO 4.11 Security Baseline & Change Detection Engine.

Features:
- Versioned, immutable baseline snapshots (v1, v2, ...)
- Evidence-backed baseline entries with observation counts and provenance
- False-positive controls: allowlisting, known_expected exceptions with optional expiration
- Bounded ChangeDetector computing before/after diffs against baseline
"""

from __future__ import annotations

from dataclasses import dataclass, field
import enum
import time
from typing import Any

from app.services.automation.operator.security.evidence import SecretRedactor, SecurityScope
from app.services.automation.operator.security.security_state import SecurityAsset, SecurityState


class BaselineStatus(enum.Enum):
    KNOWN_NORMAL = "KNOWN_NORMAL"
    UNKNOWN = "UNKNOWN"
    NEW = "NEW"
    CHANGED = "CHANGED"
    REMOVED = "REMOVED"
    EXPECTED = "EXPECTED"
    UNEXPECTED = "UNEXPECTED"


@dataclass
class BaselineEntry:
    asset_id: str
    asset_type: str
    name: str
    first_seen: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)
    observation_count: int = 1
    source: str = "psutil"
    evidence_quality: str = "HIGH"
    status: BaselineStatus = BaselineStatus.KNOWN_NORMAL
    expected_reason: str = ""
    scope: SecurityScope = SecurityScope.LOCAL_MACHINE
    expires_at: float | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return time.time() > self.expires_at

    def to_dict(self) -> dict[str, Any]:
        return {
            "asset_id": self.asset_id,
            "asset_type": self.asset_type,
            "name": self.name,
            "first_seen": self.first_seen,
            "last_seen": self.last_seen,
            "observation_count": self.observation_count,
            "source": self.source,
            "evidence_quality": self.evidence_quality,
            "status": self.status.value if hasattr(self.status, "value") else str(self.status),
            "expected_reason": self.expected_reason,
            "scope": self.scope.value if hasattr(self.scope, "value") else str(self.scope),
            "is_expired": self.is_expired(),
            "details": SecretRedactor.redact_dict(self.details),
        }


@dataclass
class BaselineDiff:
    what_changed: str
    asset_id: str
    asset_type: str
    status: BaselineStatus
    before: dict[str, Any] | None
    after: dict[str, Any] | None
    timestamp: float = field(default_factory=time.time)
    confidence: str = "HIGH"
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "what_changed": self.what_changed,
            "asset_id": self.asset_id,
            "asset_type": self.asset_type,
            "status": self.status.value if hasattr(self.status, "value") else str(self.status),
            "before": SecretRedactor.redact_dict(self.before) if self.before else None,
            "after": SecretRedactor.redact_dict(self.after) if self.after else None,
            "timestamp": self.timestamp,
            "confidence": self.confidence,
            "reason": self.reason,
        }


class SecurityBaseline:
    """Manages versioned baseline snapshots and exception allowlists."""

    def __init__(self) -> None:
        self._versions: dict[str, dict[str, BaselineEntry]] = {}
        self._history: list[dict[str, Any]] = []
        self._exceptions: dict[str, BaselineEntry] = {}
        self._current_version_id: str = "v0"
        self._init_default_known_normal()

    def _init_default_known_normal(self) -> None:
        # Pre-seed expected FALSO development server baseline
        falso_dev = BaselineEntry(
            asset_id="port_8000",
            asset_type="listening_port",
            name="Port 8000 (uvicorn)",
            status=BaselineStatus.EXPECTED,
            expected_reason="FALSO backend development server",
            details={"port": 8000, "process_name": "uvicorn", "host": "127.0.0.1"},
        )
        self._exceptions["port_8000"] = falso_dev

    def create_baseline(self, state: SecurityState, label: str = "") -> str:
        """Create a new versioned baseline snapshot from observed state."""
        version_num = len(self._versions) + 1
        v_id = f"v{version_num}"
        entries: dict[str, BaselineEntry] = {}

        assets = state.build_asset_inventory()
        for a in assets:
            entries[a.asset_id] = BaselineEntry(
                asset_id=a.asset_id,
                asset_type=a.asset_type,
                name=a.name,
                source="security_state_observer",
                evidence_quality="HIGH",
                status=BaselineStatus.KNOWN_NORMAL,
                expected_reason=label or "Standard baseline snapshot",
                scope=a.scope,
                details=a.details,
            )

        self._versions[v_id] = entries
        self._current_version_id = v_id
        self._history.append({
            "version_id": v_id,
            "label": label,
            "timestamp": time.time(),
            "asset_count": len(entries),
        })
        return v_id

    def add_allowlist_exception(self, asset_id: str, reason: str, expires_in_sec: float | None = None) -> None:
        """Add a temporary or permanent known-expected exception."""
        exp_time = (time.time() + expires_in_sec) if expires_in_sec else None
        entry = BaselineEntry(
            asset_id=asset_id,
            asset_type="exception",
            name=asset_id,
            status=BaselineStatus.EXPECTED,
            expected_reason=reason,
            expires_at=exp_time,
        )
        self._exceptions[asset_id] = entry

    def compare_baseline(self, current_state: SecurityState, version_id: str | None = None) -> list[BaselineDiff]:
        """Compare current state assets against baseline."""
        target_v = version_id or self._current_version_id
        baseline_entries = self._versions.get(target_v, {})
        diffs: list[BaselineDiff] = []

        current_assets = {a.asset_id: a for a in current_state.build_asset_inventory()}

        # 1. Detect New / Unexpected Assets
        for aid, asset in current_assets.items():
            if aid in self._exceptions and not self._exceptions[aid].is_expired():
                # Matches known expected exception
                continue

            if aid not in baseline_entries:
                diffs.append(
                    BaselineDiff(
                        what_changed=f"new_{asset.asset_type}_detected",
                        asset_id=aid,
                        asset_type=asset.asset_type,
                        status=BaselineStatus.NEW,
                        before=None,
                        after=asset.to_dict(),
                        confidence="HIGH",
                        reason=f"Asset {asset.name} is newly observed and not in baseline {target_v}.",
                    )
                )

        # 2. Detect Removed Assets
        for aid, b_entry in baseline_entries.items():
            if aid not in current_assets:
                diffs.append(
                    BaselineDiff(
                        what_changed=f"{b_entry.asset_type}_disappeared",
                        asset_id=aid,
                        asset_type=b_entry.asset_type,
                        status=BaselineStatus.REMOVED,
                        before=b_entry.to_dict(),
                        after=None,
                        confidence="HIGH",
                        reason=f"Asset {b_entry.name} from baseline {target_v} is no longer present.",
                    )
                )

        return diffs

    def restore_previous_baseline(self, version_id: str) -> bool:
        if version_id in self._versions:
            self._current_version_id = version_id
            return True
        return False

    def get_baseline_history(self) -> list[dict[str, Any]]:
        return list(self._history)


class ChangeDetector:
    """Detects security-relevant state deviations."""

    def __init__(self, baseline: SecurityBaseline | None = None) -> None:
        self.baseline = baseline or SecurityBaseline()

    def detect_changes(self, state: SecurityState) -> list[BaselineDiff]:
        return self.baseline.compare_baseline(state)


security_baseline = SecurityBaseline()
change_detector = ChangeDetector(security_baseline)
