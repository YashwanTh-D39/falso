"""
FALSO 4.11 Controlled Cybersecurity Diagnostics & Intelligence Skill.

Provides safe, controlled, scope-restricted cybersecurity diagnostic and intelligence capabilities:
- Local port & socket inspection with process mapping (PORT -> SOCKET -> PID -> PROCESS)
- DNS resolution diagnostics for authorized domains
- TCP handshake & connectivity testing
- Safe HTTP/HTTPS connectivity checks with sensitive header redaction
- Log inspection within approved workspace directories
- Baseline comparison & change detection (What changed since last baseline?)
- Anomaly investigation & security intelligence ("Is anything unusual?")
- Bounded hypothesis-driven investigation workflows

DENIES:
- Arbitrary unauthorized third-party scanning
- Credential harvesting / brute forcing
- Exploitation or payload delivery
- Arbitrary command/shell execution
"""

from __future__ import annotations

import logging
import socket
from typing import Any

from app.services.automation.operator.computer_state import ComputerState
from app.services.automation.operator.security.baseline import change_detector, security_baseline
from app.services.automation.operator.security.evidence import (
    AuthorizationStatus,
    DiagnosticBudget,
    FindingSeverity,
    SecretRedactor,
    SecurityEvidence,
    SecurityScope,
)
from app.services.automation.operator.security.investigation_engine import security_investigation_engine
from app.services.automation.operator.security.security_workflow import security_workflow
from app.services.automation.operator.security.timeline import security_timeline
from app.services.automation.operator.security.tool_registry import security_tool_registry
from app.services.automation.operator.skills.base_skill import BaseSkill
from app.services.automation.permissions import RiskLevel

logger = logging.getLogger(__name__)


class CybersecuritySkill(BaseSkill):
    name = "cybersecurity"
    allowed_applications = ["network", "diagnostics", "security", "audit", "server", "port", "dns", "http", "logs", "baseline", "timeline"]
    default_risk_level = RiskLevel.MEDIUM

    def can_handle(self, target: str, action: str) -> bool:
        t = target.lower()
        a = action.lower()
        keywords = ("security", "network", "audit", "diagnostics", "server", "port", "dns", "http", "logs", "localhost", "127.0.0.1", "baseline", "timeline", "anomaly", "unusual")
        if any(k in t for k in keywords):
            return True
        actions = ("port_check", "check_port", "dns_check", "resolve_dns", "audit_logs", "security_scan", "diagnose", "investigate", "http_check", "test_http", "test_tcp", "route_check", "baseline_check", "what_changed")
        return any(act in a for act in actions)

    def execute(self, action: str, target: str, params: dict[str, Any], state: ComputerState) -> dict[str, Any]:
        # Enforce scope: Target must be explicitly authorized or local
        host = params.get("host", "127.0.0.1")
        if host not in ("127.0.0.1", "localhost", "0.0.0.0"):
            # Check if domain is in allowed public list or explicitly authorized
            is_allowed_public = any(d in host.lower() for d in ("google.com", "github.com", "example.com", "pypi.org", "python.org"))
            if not is_allowed_public and not params.get("authorized_scope", False):
                return {
                    "success": False,
                    "error": f"Target host '{host}' is outside authorized local scope.",
                    "denied": True,
                    "verified": False,
                }

        # 1. Full Security Intelligence & Investigation Engine
        if action in ("diagnose", "security_scan", "investigate", "what_changed", "baseline_check"):
            query = params.get("query", params.get("goal", "check server status"))
            success, summary, findings = security_investigation_engine.investigate(query)
            return {
                "success": success,
                "summary": summary,
                "findings_count": len(findings),
                "findings": [f.to_dict() for f in findings],
                "verified": success,
            }

        # 2. Port Check with Process Correlation
        if action in ("port_check", "check_port"):
            port = int(params.get("port", 80))
            is_open_direct = self._check_port_open(host, port)
            tool = security_tool_registry.get_tool("inspect_port")
            res = tool.handler(port=port, host=host) if tool else {}
            is_open = is_open_direct or res.get("is_listening", False)
            sockets = res.get("sockets", [])
            pid = sockets[0].get("pid") if sockets else None
            p_name = sockets[0].get("process_name") if sockets else ""
            return {
                "success": True,
                "host": host,
                "port": port,
                "is_open": is_open,
                "pid": pid,
                "process_name": p_name,
                "verified": True,
            }

        # 3. DNS Diagnostics
        if action in ("dns_check", "resolve_dns"):
            tool = security_tool_registry.get_tool("resolve_dns")
            return tool.handler(hostname=host) if tool else {"success": False}

        # 4. HTTP Diagnostics
        if action in ("http_check", "test_http"):
            url = params.get("url", f"http://{host}:{params.get('port', 8000)}")
            tool = security_tool_registry.get_tool("test_http")
            return tool.handler(url=url) if tool else {"success": False}

        # 5. Log Inspection
        if action in ("audit_logs", "inspect_logs"):
            query = params.get("query", "error")
            tool = security_tool_registry.get_tool("inspect_logs")
            return tool.handler(query=query) if tool else {"success": False}

        # 6. Route Inspection
        if action in ("route_check", "inspect_routes"):
            tool = security_tool_registry.get_tool("inspect_routes")
            return tool.handler() if tool else {"success": False}

        # 7. Timeline Inspection
        if action in ("timeline", "get_timeline"):
            recent = security_timeline.get_recent_events(10)
            return {"success": True, "events": recent, "verified": True}

        return {"success": False, "error": f"Unsupported cybersecurity action: {action}"}

    def _check_port_open(self, host: str, port: int) -> bool:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(1.0)
                res = s.connect_ex((host, port))
                return res == 0
        except Exception:
            return False

    def verify(self, action: str, target: str, before_state: ComputerState, after_state: ComputerState, result: dict[str, Any]) -> tuple[bool, str]:
        if not result.get("success", False):
            return False, result.get("error", "Cybersecurity diagnostic failed.")
        summary = result.get("summary")
        if summary:
            return True, summary
        if action in ("port_check", "check_port"):
            p = result.get("port")
            p_name = result.get("process_name")
            if result.get("is_open"):
                return True, f"Port {p} is listening under {p_name}." if p_name else f"Port {p} is listening."
            return True, f"Nothing is listening on port {p}."
        return result.get("verified", True), "Diagnostic completed."
