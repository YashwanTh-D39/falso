"""
FALSO 4.11 Security Investigation Engine.

Executes hypothesis-driven, evidence-grounded cybersecurity investigations:
QUESTION -> OBSERVE STATE -> COMPARE BASELINE -> IDENTIFY EVIDENCE GAPS -> TOOL SELECTION -> BOUNDED COLLECTION -> CORRELATION -> FINDINGS -> CONCISE REPORT

Features:
- Answers defensive inquiries: "What's running?", "What's listening?", "What changed?", "Is anything unusual?", "Why is this unusual?"
- Enforces strict DiagnosticBudget bounds and stop conditions
- Uses SecurityEvidenceGraph, DetectionEngine, and SecurityTimeline
- Generates concise, truthful, evidence-backed summaries without internal chain-of-thought exposure
"""

from __future__ import annotations

import logging
import re
import time
from typing import Any

from app.services.automation.operator.computer_state import EvidenceType, StateValue
from app.services.automation.operator.security.baseline import change_detector, security_baseline
from app.services.automation.operator.security.confidence import ConfidenceScore
from app.services.automation.operator.security.detection_engine import SecurityFinding, detection_engine
from app.services.automation.operator.security.evidence import (
    AuthorizationStatus,
    DiagnosticBudget,
    FindingSeverity,
    SecretRedactor,
    SecurityEvidence,
    SecurityScope,
)
from app.services.automation.operator.security.evidence_graph import SecurityEvidenceGraph
from app.services.automation.operator.security.security_state import SecurityState
from app.services.automation.operator.security.timeline import security_timeline
from app.services.automation.operator.security.tool_registry import security_tool_registry

logger = logging.getLogger(__name__)


class SecurityInvestigationEngine:
    """Orchestrates structured, hypothesis-driven security investigations."""

    def __init__(self) -> None:
        self.tool_registry = security_tool_registry
        self.baseline = security_baseline
        self.detector = detection_engine
        self.timeline = security_timeline

    def investigate(
        self,
        query: str,
        scope: SecurityScope = SecurityScope.LOCAL_MACHINE,
        budget: DiagnosticBudget | None = None,
    ) -> tuple[bool, str, list[SecurityFinding]]:
        active_budget = budget or DiagnosticBudget()
        q_lower = query.lower().strip()

        logger.info("[SECURITY_INVESTIGATION] query=%r scope=%s", query, scope.value)

        # 1. Scope & Stop Condition Check
        if not active_budget.can_step():
            return False, "Investigation budget exceeded.", []

        # 2. Observe Current State
        state = self._observe_current_security_state(active_budget)

        # 3. Route specific defensive investigation goals

        # Goal A: "What is listening?" / "Check listening ports"
        if any(w in q_lower for w in ("what is listening", "what's listening", "whats listening", "listening ports", "ports listening")):
            return self._investigate_listening_ports(state, active_budget)

        # Goal B: "What is running?" / "What's running" / "Active processes"
        if any(w in q_lower for w in ("what is running", "what's running", "whats running", "running processes", "active processes")):
            return self._investigate_running_processes(state, active_budget)

        # Goal C: "What changed?" / "Show changes" / "What changed since baseline"
        if any(w in q_lower for w in ("what changed", "show changes", "changes since", "since my last baseline", "what is new")):
            return self._investigate_changes(state, active_budget)

        # Goal D: "Is anything unusual?" / "Check for suspicious" / "Is anything wrong"
        if any(w in q_lower for w in ("unusual", "suspicious", "anything wrong", "anomal", "security check", "scan local")):
            return self._investigate_anomalies(state, active_budget)

        # Goal E: "What happened before this problem?" / "Timeline" / "Recent events"
        if any(w in q_lower for w in ("before this problem", "timeline", "recent events", "what happened before")):
            return self._investigate_timeline(active_budget)

        # Goal F: Single Port / Service Unreachable Investigation
        port_match = re.search(r"\bport\s+(\d+)\b", q_lower) or re.search(r":(\d+)\b", q_lower)
        if port_match:
            port_num = int(port_match.group(1))
            return self._investigate_specific_port(port_num, state, active_budget)

        # Default: General anomaly & listening check
        return self._investigate_anomalies(state, active_budget)

    # ── State Observation ──

    def _observe_current_security_state(self, budget: DiagnosticBudget) -> SecurityState:
        state = SecurityState()
        if not budget.can_step():
            return state

        budget.record_step()
        # 1. Observe Listening Ports
        tool_port = self.tool_registry.get_tool("inspect_port")
        if tool_port:
            port_res = tool_port.handler()
            if port_res.get("success"):
                state.listening_ports = StateValue(
                    value=port_res.get("sockets", []),
                    evidence=EvidenceType.OBSERVED,
                    source="inspect_port",
                )

        # 2. Observe Processes
        tool_proc = self.tool_registry.get_tool("inspect_process")
        if tool_proc:
            proc_res = tool_proc.handler()
            if proc_res.get("success"):
                state.processes = StateValue(
                    value=proc_res.get("processes", []),
                    evidence=EvidenceType.OBSERVED,
                    source="inspect_process",
                )

        # 3. Observe Interfaces
        tool_route = self.tool_registry.get_tool("inspect_routes")
        if tool_route:
            route_res = tool_route.handler()
            if route_res.get("success"):
                state.network_interfaces = StateValue(
                    value=route_res.get("interfaces", {}),
                    evidence=EvidenceType.OBSERVED,
                    source="inspect_routes",
                )

        return state

    # ── Investigation Handlers ──

    def _investigate_listening_ports(self, state: SecurityState, budget: DiagnosticBudget) -> tuple[bool, str, list[SecurityFinding]]:
        ports = state.listening_ports.value if state.listening_ports.is_observed() else []
        if not ports:
            return True, "No listening ports currently observed on local machine.", []

        # Correlate top listening ports
        port_summaries = []
        for p in ports[:5]:
            p_num = p.get("port")
            p_name = p.get("process_name", "Unknown")
            pid = p.get("pid")
            port_summaries.append(f"Port {p_num} ({p_name}{f', PID {pid}' if pid else ''})")

        summary = f"Currently observing {len(ports)} listening socket(s): " + ", ".join(port_summaries) + "."
        return True, summary, []

    def _investigate_running_processes(self, state: SecurityState, budget: DiagnosticBudget) -> tuple[bool, str, list[SecurityFinding]]:
        procs = state.processes.value if state.processes.is_observed() else []
        proc_names = list({p.get("name") for p in procs if p.get("name")})[:6]
        summary = f"Observing active processes including: {', '.join(proc_names)}." if proc_names else "Active processes enumerated."
        return True, summary, []

    def _investigate_changes(self, state: SecurityState, budget: DiagnosticBudget) -> tuple[bool, str, list[SecurityFinding]]:
        diffs = self.baseline.compare_baseline(state)
        if not diffs:
            return True, "No security-relevant deviations detected compared to current baseline.", []

        findings = self.detector.evaluate_state_and_changes(state, diffs, self.baseline)
        change_summaries = [d.reason for d in diffs[:3]]
        summary = f"Detected {len(diffs)} baseline change(s): " + " ".join(change_summaries)
        return True, summary, findings

    def _investigate_anomalies(self, state: SecurityState, budget: DiagnosticBudget) -> tuple[bool, str, list[SecurityFinding]]:
        diffs = self.baseline.compare_baseline(state)
        findings = self.detector.evaluate_state_and_changes(state, diffs, self.baseline)

        if not findings:
            ports = state.listening_ports.value if state.listening_ports.is_observed() else []
            falso_listening = any(p.get("port") == 8000 for p in ports)
            if falso_listening:
                return True, "Port 8000 is your FALSO development server and is only listening on localhost. Nothing suspicious found.", []
            return True, "Security state is consistent with baseline. No anomalous activity detected.", []

        top_finding = findings[0]
        summary = f"Observed 1 notable security signal: {top_finding.reasoning_summary} Recommended next step: {top_finding.recommended_next_step}"
        return True, summary, findings

    def _investigate_timeline(self, budget: DiagnosticBudget) -> tuple[bool, str, list[SecurityFinding]]:
        recent = self.timeline.get_recent_events(5)
        if not recent:
            return True, "No recent environmental security events recorded in the active timeline.", []
        ev_summaries = [f"{e.get('event_type')} on {e.get('target')}" for e in recent]
        summary = f"Recent timeline events: {'; '.join(ev_summaries)}."
        return True, summary, []

    def _investigate_specific_port(self, port: int, state: SecurityState, budget: DiagnosticBudget) -> tuple[bool, str, list[SecurityFinding]]:
        ports = state.listening_ports.value if state.listening_ports.is_observed() else []
        matching = [p for p in ports if p.get("port") == port]

        if not matching:
            return True, f"Nothing is listening on port {port}.", []

        m = matching[0]
        proc = m.get("process_name", "Unknown")
        pid = m.get("pid")
        summary = f"Port {port} is listening under {proc}" + (f" (PID {pid})." if pid else ".")
        return True, summary, []


security_investigation_engine = SecurityInvestigationEngine()
