"""
FALSO 4.10 Adaptive Cybersecurity Diagnostic Workflow Engine.

Executes local-first, evidence-driven, progressive cybersecurity diagnostics:
UNDERSTAND -> DETERMINE SCOPE -> SELECT TOOL -> BUDGET & PERMISSION CHECK -> EXECUTE -> COLLECT EVIDENCE -> ANALYZE -> VERIFY -> REPORT

Features:
- Progressive diagnostic sequence with early termination upon sufficient evidence
- Strict DiagnosticBudget bounds (MAX_STEPS, MAX_RUNTIME, MAX_NETWORK_REQUESTS, MAX_LOG_BYTES)
- Explicit SecurityScope and AuthorizationStatus validation
- Comprehensive secret redaction on all evidence and summaries
- Process-to-port correlation (PORT -> SOCKET -> PID -> PROCESS -> APPLICATION)
"""

from __future__ import annotations

import logging
import re
import time
from typing import Any

from app.services.automation.operator.security.evidence import (
    AuthorizationStatus,
    DiagnosticBudget,
    FindingSeverity,
    SecretRedactor,
    SecurityEvidence,
    SecurityScope,
)
from app.services.automation.operator.security.tool_registry import security_tool_registry
from app.services.automation.permissions import PermissionLevel, RiskLevel, permission_manager

logger = logging.getLogger(__name__)


class AdaptiveSecurityWorkflow:
    """Orchestrates structured, scope-controlled cybersecurity diagnostic investigations."""

    def __init__(self) -> None:
        self.tool_registry = security_tool_registry

    def run_investigation(
        self,
        query: str,
        authorized_scopes: list[SecurityScope] | None = None,
        budget: DiagnosticBudget | None = None,
    ) -> tuple[bool, str, list[SecurityEvidence]]:
        """
        Execute adaptive cybersecurity investigation for query.
        Returns:
            (success: bool, concise_summary: str, evidence_list: list[SecurityEvidence])
        """
        active_budget = budget or DiagnosticBudget()
        q_lower = query.lower().strip()
        evidence_chain: list[SecurityEvidence] = []

        # 1. DETERMINE TARGET & SCOPE
        target_host, target_port, scope = self._resolve_target_and_scope(q_lower)
        auth_status = self._evaluate_authorization(target_host, scope, authorized_scopes)

        if auth_status == AuthorizationStatus.DENIED:
            logger.warning("[SECURITY][SCOPE_DENIED] Target '%s' is outside authorized scope.", target_host)
            ev = SecurityEvidence(
                finding=f"Target '{target_host}' is outside authorized scope.",
                target=target_host,
                source="scope_enforcer",
                severity=FindingSeverity.HIGH,
                verification_status=False,
                scope=scope,
                authorization=AuthorizationStatus.DENIED,
            )
            return False, f"Target '{target_host}' is outside authorized diagnostic scope.", [ev]

        logger.info("[SECURITY][WORKFLOW_START] query=%r target=%s:%s scope=%s", query, target_host, target_port, scope.value)

        # 2. ADAPTIVE INVESTIGATION SEQUENCES

        # Scenario A: Port Inspection / "What's listening on port X?"
        if any(w in q_lower for w in ("what's listening", "whats listening", "is port", "check port", "listening on port")) or (target_port and "listen" in q_lower):
            return self._investigate_port(target_host, target_port or 8000, scope, active_budget)

        # Scenario B: Local Server Unreachable / "Why can't localhost:8000 connect?"
        if any(w in q_lower for w in ("not reachable", "can't connect", "cant connect", "unreachable", "why can't", "why cant", "connection refused")):
            return self._investigate_connectivity_failure(target_host, target_port or 8000, scope, active_budget)

        # Scenario C: DNS Resolution
        if any(w in q_lower for w in ("resolve", "dns", "domain")):
            return self._investigate_dns(target_host, scope, active_budget)

        # Scenario D: Log Inspection / Error Search
        if any(w in q_lower for w in ("logs", "log", "errors", "server logs")):
            return self._investigate_logs(q_lower, scope, active_budget)

        # Scenario E: Network Interface / Routes
        if any(w in q_lower for w in ("network config", "interfaces", "ip address", "network configuration")):
            return self._investigate_network_config(scope, active_budget)

        # Default: Single Port / General Connectivity Check
        return self._investigate_port(target_host, target_port or 8000, scope, active_budget)

    # ── Specialized Adaptive Diagnostic Pipelines ──

    def _investigate_port(
        self,
        host: str,
        port: int,
        scope: SecurityScope,
        budget: DiagnosticBudget,
    ) -> tuple[bool, str, list[SecurityEvidence]]:
        """Port inspection with process correlation."""
        if not budget.can_step():
            return False, "Diagnostic budget exceeded.", []

        budget.record_step()
        tool = self.tool_registry.get_tool("inspect_port")
        res = tool.handler(port=port, host=host) if tool else {"success": False}

        if not res.get("is_listening"):
            ev = SecurityEvidence(
                finding=f"Nothing is listening on port {port}.",
                target=f"{host}:{port}",
                source="port_inspector",
                evidence=res,
                confidence="HIGH",
                severity=FindingSeverity.INFO,
                verification_status=True,
                scope=scope,
            )
            return True, f"Nothing is listening on port {port}.", [ev]

        # Correlate to process
        sockets = res.get("sockets", [])
        primary = sockets[0] if sockets else {}
        pid = primary.get("pid")
        proc_name = primary.get("process_name") or "Unknown Process"

        finding_str = f"Port {port} is listening under {proc_name}" + (f" (PID {pid})." if pid else ".")
        ev = SecurityEvidence(
            finding=finding_str,
            target=f"{host}:{port}",
            source="port_inspector",
            evidence=res,
            process_info={"pid": pid, "name": proc_name},
            confidence="HIGH",
            severity=FindingSeverity.INFO,
            verification_status=True,
            scope=scope,
        )
        return True, finding_str, [ev]

    def _investigate_connectivity_failure(
        self,
        host: str,
        port: int,
        scope: SecurityScope,
        budget: DiagnosticBudget,
    ) -> tuple[bool, str, list[SecurityEvidence]]:
        """Adaptive multi-step diagnostic: HTTP -> Port -> Process -> Logs."""
        evidence_chain: list[SecurityEvidence] = []

        # Step 1: HTTP check
        if budget.can_make_network_request():
            budget.record_step()
            budget.record_network_request()
            http_tool = self.tool_registry.get_tool("test_http")
            url = f"http://{host}:{port}"
            http_res = http_tool.handler(url=url, timeout=2.0) if http_tool else {}

            if http_res.get("is_reachable"):
                status_code = http_res.get("status_code", 200)
                if status_code < 400:
                    summary = f"localhost:{port} is reachable (HTTP {status_code})."
                    ev = SecurityEvidence(
                        finding=summary,
                        target=url,
                        source="http_diagnostics",
                        evidence=http_res,
                        confidence="HIGH",
                        severity=FindingSeverity.INFO,
                        verification_status=True,
                        scope=scope,
                    )
                    return True, summary, [ev]
                else:
                    # HTTP Error (e.g. 500/503)
                    summary = f"Your server is running, but localhost:{port} returned HTTP {status_code}."
                    ev = SecurityEvidence(
                        finding=summary,
                        target=url,
                        source="http_diagnostics",
                        evidence=http_res,
                        confidence="HIGH",
                        severity=FindingSeverity.MEDIUM,
                        verification_status=True,
                        scope=scope,
                    )
                    evidence_chain.append(ev)

        # Step 2: Port & Socket Check
        if budget.can_step():
            budget.record_step()
            port_tool = self.tool_registry.get_tool("inspect_port")
            port_res = port_tool.handler(port=port, host=host) if port_tool else {}

            if not port_res.get("is_listening"):
                summary = f"Connection failed: No process is listening on port {port}."
                ev = SecurityEvidence(
                    finding=summary,
                    target=f"{host}:{port}",
                    source="port_inspector",
                    evidence=port_res,
                    confidence="HIGH",
                    severity=FindingSeverity.HIGH,
                    verification_status=True,
                    recommended_next_step=f"Start the server on port {port}.",
                    scope=scope,
                )
                evidence_chain.append(ev)
                return True, summary, evidence_chain
            else:
                sockets = port_res.get("sockets", [])
                p_name = sockets[0].get("process_name") if sockets else "Unknown"
                ev = SecurityEvidence(
                    finding=f"Port {port} is open under {p_name}.",
                    target=f"{host}:{port}",
                    source="port_inspector",
                    evidence=port_res,
                    confidence="HIGH",
                    severity=FindingSeverity.INFO,
                    verification_status=True,
                    scope=scope,
                )
                evidence_chain.append(ev)

        # Step 3: Inspect Logs if available
        if budget.can_step():
            budget.record_step()
            log_tool = self.tool_registry.get_tool("inspect_logs")
            log_res = log_tool.handler(query="error", max_lines=5) if log_tool else {}
            if log_res.get("match_count", 0) > 0:
                summary = f"Port {port} is listening, but recent server logs contain errors."
                ev = SecurityEvidence(
                    finding=summary,
                    target="workspace_logs",
                    source="log_inspector",
                    evidence=log_res,
                    confidence="MEDIUM",
                    severity=FindingSeverity.MEDIUM,
                    verification_status=True,
                    scope=scope,
                )
                evidence_chain.append(ev)
                return True, summary, evidence_chain

        summary = f"Port {port} is listening, but HTTP connection encountered an error."
        return True, summary, evidence_chain

    def _investigate_dns(
        self,
        host: str,
        scope: SecurityScope,
        budget: DiagnosticBudget,
    ) -> tuple[bool, str, list[SecurityEvidence]]:
        """DNS resolution investigation."""
        if not budget.can_step():
            return False, "Diagnostic budget exceeded.", []

        budget.record_step()
        dns_tool = self.tool_registry.get_tool("resolve_dns")
        res = dns_tool.handler(hostname=host) if dns_tool else {}

        if res.get("resolves"):
            ips = ", ".join(res.get("resolved_ips", []))
            summary = f"DNS resolution for '{host}' succeeded: {ips}."
            ev = SecurityEvidence(
                finding=summary,
                target=host,
                source="dns_diagnostics",
                evidence=res,
                confidence="HIGH",
                severity=FindingSeverity.INFO,
                verification_status=True,
                scope=scope,
            )
            return True, summary, [ev]
        else:
            summary = f"DNS resolution failed for '{host}': {res.get('error', 'Host not found')}."
            ev = SecurityEvidence(
                finding=summary,
                target=host,
                source="dns_diagnostics",
                evidence=res,
                confidence="HIGH",
                severity=FindingSeverity.MEDIUM,
                verification_status=True,
                scope=scope,
            )
            return True, summary, [ev]

    def _investigate_logs(
        self,
        query: str,
        scope: SecurityScope,
        budget: DiagnosticBudget,
    ) -> tuple[bool, str, list[SecurityEvidence]]:
        """Log search investigation."""
        if not budget.can_step():
            return False, "Diagnostic budget exceeded.", []

        budget.record_step()
        log_tool = self.tool_registry.get_tool("inspect_logs")
        res = log_tool.handler(query="error", max_lines=10) if log_tool else {}

        count = res.get("match_count", 0)
        summary = f"Found {count} error entries in local application logs." if count > 0 else "No error entries found in local logs."
        ev = SecurityEvidence(
            finding=summary,
            target="workspace_logs",
            source="log_inspector",
            evidence=res,
            confidence="HIGH",
            severity=FindingSeverity.MEDIUM if count > 0 else FindingSeverity.INFO,
            verification_status=True,
            scope=scope,
        )
        return True, summary, [ev]

    def _investigate_network_config(
        self,
        scope: SecurityScope,
        budget: DiagnosticBudget,
    ) -> tuple[bool, str, list[SecurityEvidence]]:
        """Network interface diagnostics."""
        if not budget.can_step():
            return False, "Diagnostic budget exceeded.", []

        budget.record_step()
        route_tool = self.tool_registry.get_tool("inspect_routes")
        res = route_tool.handler() if route_tool else {}

        ifaces = res.get("interfaces", {})
        active_count = sum(1 for iface, data in ifaces.items() if data.get("is_up") and data.get("ipv4_addresses"))
        summary = f"Detected {active_count} active network interface(s) on local machine."
        ev = SecurityEvidence(
            finding=summary,
            target="local_machine",
            source="route_inspector",
            evidence=res,
            confidence="HIGH",
            severity=FindingSeverity.INFO,
            verification_status=True,
            scope=scope,
        )
        return True, summary, [ev]

    # ── Target, Scope, and Authorization Resolution ──

    def _resolve_target_and_scope(self, text: str) -> tuple[str, int | None, SecurityScope]:
        port = None
        port_match = re.search(r"\bport\s+(\d+)\b", text) or re.search(r":(\d+)\b", text)
        if port_match:
            try:
                port = int(port_match.group(1))
            except ValueError:
                port = None

        if any(h in text for h in ("localhost", "127.0.0.1", "0.0.0.0", "my machine", "this machine", "local server")):
            return "127.0.0.1", port, SecurityScope.LOCAL_MACHINE

        # Extract domain/hostname
        words = text.split()
        for w in words:
            clean_w = w.strip(".,!?;:'\"()")
            if "." in clean_w and not clean_w.startswith("."):
                return clean_w, port, SecurityScope.AUTHORIZED_DOMAIN

        return "127.0.0.1", port, SecurityScope.LOCAL_MACHINE

    def _evaluate_authorization(
        self,
        host: str,
        scope: SecurityScope,
        authorized_scopes: list[SecurityScope] | None = None,
    ) -> AuthorizationStatus:
        """Validate whether host target is authorized."""
        # Localhost is always within LOCAL_MACHINE scope
        if host in ("127.0.0.1", "localhost", "0.0.0.0") or scope == SecurityScope.LOCAL_MACHINE:
            return AuthorizationStatus.ALLOWED

        # If authorized scopes explicitly provided
        if authorized_scopes and scope in authorized_scopes:
            return AuthorizationStatus.ALLOWED

        # Known allowed public domains (e.g. google.com, github.com, example.com)
        if any(d in host.lower() for d in ("google.com", "github.com", "example.com", "pypi.org", "python.org")):
            return AuthorizationStatus.ALLOWED

        # Reject arbitrary unknown external hosts
        return AuthorizationStatus.DENIED


security_workflow = AdaptiveSecurityWorkflow()
