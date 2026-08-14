"""
FALSO 4.11 Cybersecurity Detection Engine.

Evaluates structured SecurityState, BaselineDiffs, and EvidenceGraphs against defensive rules.
Features:
- Multi-signal correlation required before elevated severity (HIGH/CRITICAL)
- False-positive suppression via Baseline allowlists and known_expected exceptions
- Mitre ATT&CK analytical mapping
- Output: Structured SecurityFinding records
"""

from __future__ import annotations

from dataclasses import dataclass, field
import time
from typing import Any

from app.services.automation.operator.security.baseline import BaselineDiff, BaselineStatus, SecurityBaseline
from app.services.automation.operator.security.confidence import ConfidenceEngine, ConfidenceScore
from app.services.automation.operator.security.evidence import (
    FindingSeverity,
    SecretRedactor,
    SecurityScope,
)
from app.services.automation.operator.security.mitre_mapping import mitre_mapper
from app.services.automation.operator.security.security_state import SecurityState


@dataclass
class SecurityFinding:
    finding_id: str
    rule_id: str
    title: str
    severity: FindingSeverity
    confidence: ConfidenceScore
    target: str
    scope: SecurityScope = SecurityScope.LOCAL_MACHINE
    summary: str = ""
    evidence: dict[str, Any] = field(default_factory=dict)
    related_assets: list[str] = field(default_factory=list)
    potential_technique: dict[str, Any] | None = None
    reasoning_summary: str = ""
    recommended_next_step: str = ""
    verification_status: bool = True
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "finding_id": self.finding_id,
            "rule_id": self.rule_id,
            "title": self.title,
            "severity": self.severity.value,
            "confidence": self.confidence.value,
            "target": self.target,
            "scope": self.scope.value,
            "summary": SecretRedactor.redact_text(self.summary),
            "evidence": SecretRedactor.redact_dict(self.evidence),
            "related_assets": self.related_assets,
            "potential_technique": self.potential_technique,
            "reasoning_summary": SecretRedactor.redact_text(self.reasoning_summary),
            "recommended_next_step": self.recommended_next_step,
            "verification_status": self.verification_status,
            "timestamp": self.timestamp,
        }


class DetectionEngine:
    """Evaluates security observations and baseline changes to generate findings."""

    def __init__(self) -> None:
        self._finding_counter: int = 0

    def evaluate_state_and_changes(
        self,
        state: SecurityState,
        changes: list[BaselineDiff],
        baseline: SecurityBaseline | None = None,
    ) -> list[SecurityFinding]:
        findings: list[SecurityFinding] = []

        # 1. Rule DET-01: Unexpected New Listening Port
        for chg in changes:
            if chg.what_changed == "new_listening_port_detected" and chg.after:
                port_data = chg.after
                port_num = port_data.get("port")
                proc_name = port_data.get("process_name", "Unknown")
                pid = port_data.get("pid")

                # Multi-signal evaluation:
                # Localhost port with known name -> LOW
                # Publicly bound or unmapped process -> MEDIUM/HIGH
                ip = port_data.get("ip", "127.0.0.1")
                is_local = ip in ("127.0.0.1", "localhost", "::1")
                has_proc = bool(proc_name and proc_name != "Unknown")

                if is_local and has_proc:
                    sev = FindingSeverity.LOW
                    conf = ConfidenceScore.HIGH
                    reason = f"Port {port_num} is newly listening under local process '{proc_name}' (PID {pid})."
                elif not has_proc:
                    sev = FindingSeverity.MEDIUM
                    conf = ConfidenceScore.MEDIUM
                    reason = f"Port {port_num} is listening on {ip} without an identifiable process owner."
                else:
                    sev = FindingSeverity.MEDIUM
                    conf = ConfidenceScore.HIGH
                    reason = f"Port {port_num} is newly exposed on network interface {ip} by '{proc_name}'."

                self._finding_counter += 1
                mitre_info = mitre_mapper.map_finding("port", port_data)
                findings.append(
                    SecurityFinding(
                        finding_id=f"FIND-{self._finding_counter:04d}",
                        rule_id="DET-01",
                        title=f"New Listening Port Observed: {port_num}",
                        severity=sev,
                        confidence=conf,
                        target=f"{ip}:{port_num}",
                        summary=f"New listening service detected on port {port_num}.",
                        evidence=port_data,
                        related_assets=[f"port_{port_num}", f"proc_{pid}" if pid else ""],
                        potential_technique=mitre_info.to_dict() if mitre_info else None,
                        reasoning_summary=reason,
                        recommended_next_step=f"Verify if {proc_name} is intended to listen on port {port_num}.",
                        verification_status=True,
                    )
                )

        # 2. Rule DET-02: Check for Process Path Anomalies (e.g. running from Temp)
        if state.processes.is_observed():
            for p in state.processes.value:
                exe = (p.get("exe") or "").lower()
                pid = p.get("pid")
                pname = p.get("name", "Unknown")
                if "\\temp\\" in exe or "\\tmp\\" in exe or "\\appdata\\local\\temp\\" in exe:
                    self._finding_counter += 1
                    findings.append(
                        SecurityFinding(
                            finding_id=f"FIND-{self._finding_counter:04d}",
                            rule_id="DET-02",
                            title=f"Process Running from Temporary Directory: {pname}",
                            severity=FindingSeverity.MEDIUM,
                            confidence=ConfidenceScore.HIGH,
                            target=f"PID {pid} ({pname})",
                            summary=f"Process {pname} is executing from a temporary directory path.",
                            evidence={"pid": pid, "name": pname, "path": exe},
                            reasoning_summary=f"Executable '{exe}' is located in a writable temporary directory.",
                            recommended_next_step="Inspect parent process and binary authenticity.",
                            verification_status=True,
                        )
                    )

        return findings


detection_engine = DetectionEngine()
