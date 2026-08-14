"""
FALSO 4.11 Security State Model & Asset Inventory.

Represents current security posture with strict evidence classification:
- EvidenceType.OBSERVED (authoritative data from psutil/OS/sockets)
- EvidenceType.INFERRED (hypothesized/correlated metadata)
- EvidenceType.UNKNOWN (explicitly missing or unverified data)

Supports:
- Structured Asset Inventory (Host -> Interface -> Process -> Socket -> Port)
- State Snapshots & Diffs
- Unknowns Tracking
"""

from __future__ import annotations

from dataclasses import dataclass, field
import platform
import time
from typing import Any

from app.services.automation.operator.computer_state import EvidenceType, StateValue
from app.services.automation.operator.security.evidence import (
    EvidenceProvenance,
    FindingSeverity,
    SecretRedactor,
    SecurityEvidence,
    SecurityScope,
)


@dataclass
class SecurityAsset:
    asset_id: str
    asset_type: str  # "process", "listening_port", "interface", "service", "application"
    name: str
    details: dict[str, Any] = field(default_factory=dict)
    pid: int | None = None
    port: int | None = None
    ip: str | None = None
    executable_path: str | None = None
    scope: SecurityScope = SecurityScope.LOCAL_MACHINE
    evidence_type: EvidenceType = EvidenceType.OBSERVED
    first_seen: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "asset_id": self.asset_id,
            "asset_type": self.asset_type,
            "name": self.name,
            "details": SecretRedactor.redact_dict(self.details),
            "pid": self.pid,
            "port": self.port,
            "ip": self.ip,
            "executable_path": self.executable_path,
            "scope": self.scope.value if hasattr(self.scope, "value") else str(self.scope),
            "evidence_type": self.evidence_type.value if hasattr(self.evidence_type, "value") else str(self.evidence_type),
            "first_seen": self.first_seen,
            "last_seen": self.last_seen,
        }


@dataclass
class SecurityState:
    """Represents current observed security posture of the computer."""
    timestamp: float = field(default_factory=time.time)
    host_name: StateValue[str] = field(default_factory=lambda: StateValue(value=platform.node(), evidence=EvidenceType.OBSERVED))
    os_version: StateValue[str] = field(default_factory=lambda: StateValue(value=platform.platform(), evidence=EvidenceType.OBSERVED))
    network_interfaces: StateValue[dict[str, Any]] = field(default_factory=lambda: StateValue(value={}, evidence=EvidenceType.UNKNOWN))
    ip_addresses: StateValue[list[str]] = field(default_factory=lambda: StateValue(value=[], evidence=EvidenceType.UNKNOWN))
    listening_ports: StateValue[list[dict[str, Any]]] = field(default_factory=lambda: StateValue(value=[], evidence=EvidenceType.UNKNOWN))
    processes: StateValue[list[dict[str, Any]]] = field(default_factory=lambda: StateValue(value=[], evidence=EvidenceType.UNKNOWN))
    services: StateValue[list[dict[str, Any]]] = field(default_factory=lambda: StateValue(value=[], evidence=EvidenceType.UNKNOWN))
    active_connections: StateValue[list[dict[str, Any]]] = field(default_factory=lambda: StateValue(value=[], evidence=EvidenceType.UNKNOWN))
    log_events: StateValue[list[dict[str, Any]]] = field(default_factory=lambda: StateValue(value=[], evidence=EvidenceType.UNKNOWN))
    security_configuration: StateValue[dict[str, Any]] = field(default_factory=lambda: StateValue(value={}, evidence=EvidenceType.UNKNOWN))
    startup_items: StateValue[list[dict[str, Any]]] = field(default_factory=lambda: StateValue(value=[], evidence=EvidenceType.UNKNOWN))
    collected_evidences: list[SecurityEvidence] = field(default_factory=list)

    def snapshot(self) -> dict[str, Any]:
        """Produce a serialized immutable snapshot of current state."""
        return {
            "timestamp": self.timestamp,
            "host_name": self.host_name.value,
            "os_version": self.os_version.value,
            "network_interfaces": self.network_interfaces.value,
            "ip_addresses": self.ip_addresses.value,
            "listening_ports": self.listening_ports.value,
            "processes_count": len(self.processes.value) if isinstance(self.processes.value, list) else 0,
            "listening_ports_count": len(self.listening_ports.value) if isinstance(self.listening_ports.value, list) else 0,
            "evidence_count": len(self.collected_evidences),
        }

    def get_unknowns(self) -> list[str]:
        """Identify which security categories remain unobserved / UNKNOWN."""
        unknowns = []
        for attr_name in ("network_interfaces", "ip_addresses", "listening_ports", "processes", "services", "active_connections", "log_events", "security_configuration", "startup_items"):
            val: StateValue[Any] = getattr(self, attr_name)
            if val.is_unknown():
                unknowns.append(attr_name)
        return unknowns

    def merge_evidence(self, ev: SecurityEvidence) -> None:
        """Add new evidence without losing provenance."""
        self.collected_evidences.append(ev)

    def build_asset_inventory(self) -> list[SecurityAsset]:
        """Build structured correlated asset inventory from observed state."""
        assets: list[SecurityAsset] = []

        # 1. Listening Ports & Associated Sockets
        if self.listening_ports.is_observed():
            for p in self.listening_ports.value:
                port_num = p.get("port")
                pid = p.get("pid")
                proc_name = p.get("process_name", "Unknown")
                assets.append(
                    SecurityAsset(
                        asset_id=f"port_{port_num}",
                        asset_type="listening_port",
                        name=f"Port {port_num} ({proc_name})",
                        details=p,
                        pid=pid,
                        port=port_num,
                        ip=p.get("ip", "127.0.0.1"),
                        evidence_type=EvidenceType.OBSERVED,
                    )
                )

        # 2. Processes
        if self.processes.is_observed():
            for pr in self.processes.value:
                pid = pr.get("pid")
                pname = pr.get("name", "Unknown")
                assets.append(
                    SecurityAsset(
                        asset_id=f"proc_{pid}",
                        asset_type="process",
                        name=pname,
                        details=pr,
                        pid=pid,
                        executable_path=pr.get("exe"),
                        evidence_type=EvidenceType.OBSERVED,
                    )
                )

        # 3. Interfaces
        if self.network_interfaces.is_observed():
            for iface_name, iface_data in self.network_interfaces.value.items():
                assets.append(
                    SecurityAsset(
                        asset_id=f"iface_{iface_name}",
                        asset_type="interface",
                        name=iface_name,
                        details=iface_data,
                        ip=iface_data.get("ipv4_addresses", [""])[0] if iface_data.get("ipv4_addresses") else None,
                        evidence_type=EvidenceType.OBSERVED,
                    )
                )

        return assets

    def get_changes(self, previous_state: SecurityState) -> list[dict[str, Any]]:
        """Compute structured diff against previous state."""
        changes: list[dict[str, Any]] = []

        # Port changes
        curr_ports = {p.get("port"): p for p in self.listening_ports.value} if isinstance(self.listening_ports.value, list) else {}
        prev_ports = {p.get("port"): p for p in previous_state.listening_ports.value} if isinstance(previous_state.listening_ports.value, list) else {}

        # New ports
        for port, pinfo in curr_ports.items():
            if port not in prev_ports:
                changes.append({
                    "what_changed": "listening_port_opened",
                    "target": f"Port {port}",
                    "before": None,
                    "after": pinfo,
                    "timestamp": time.time(),
                    "confidence": "HIGH",
                })

        # Closed ports
        for port, pinfo in prev_ports.items():
            if port not in curr_ports:
                changes.append({
                    "what_changed": "listening_port_closed",
                    "target": f"Port {port}",
                    "before": pinfo,
                    "after": None,
                    "timestamp": time.time(),
                    "confidence": "HIGH",
                })

        return changes
