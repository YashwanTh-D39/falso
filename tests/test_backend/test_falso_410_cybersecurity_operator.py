"""
FALSO 4.10 Cybersecurity Skill & Tool Operator Tests.

Tests:
1. SecurityToolRegistry tool definitions and safety
2. SecurityScope & AuthorizationStatus distinction (no UNAUTHORIZED in SecurityScope)
3. SecretRedactor on text, dicts, HTTP headers, JWTs, and .env assignments
4. DiagnosticBudget bounds and step/request limit enforcement
5. Port inspection & Process-to-Port correlation
6. DNS resolution diagnostics
7. TCP handshake connectivity diagnostics
8. HTTP diagnostics with sensitive header redaction
9. Log inspection with error matching and byte limits
10. Route / Network interface inspection
11. AdaptiveSecurityWorkflow local-first progressive sequencing
12. Scope enforcement & unauthorized target denial
13. Command injection prevention (no arbitrary shell execution)
14. ActionSelector cybersecurity intent routing
15. OperatorEngine integration & concise responses
16. Interruption & cancellation safety
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch
import pytest

from app.services.automation.operator.action_selector import ControlMethod, action_selector
from app.services.automation.operator.computer_state import ComputerState
from app.services.automation.operator.operator_engine import operator_engine
from app.services.automation.operator.security.evidence import (
    AuthorizationStatus,
    DiagnosticBudget,
    FindingSeverity,
    SecretRedactor,
    SecurityEvidence,
    SecurityScope,
)
from app.services.automation.operator.security.security_workflow import security_workflow
from app.services.automation.operator.security.tool_registry import (
    SecurityToolDefinition,
    security_tool_registry,
)
from app.services.automation.operator.skills.cybersecurity_skill import CybersecuritySkill


class TestFalso410CybersecurityOperator:
    # ── 1. SecurityScope & AuthorizationStatus ──
    def test_01_security_scope_and_authorization_models(self):
        # Verify SecurityScope does NOT contain UNAUTHORIZED
        scope_names = [s.name for s in SecurityScope]
        assert "UNAUTHORIZED" not in scope_names
        assert "LOCAL_MACHINE" in scope_names
        assert "LOCAL_NETWORK" in scope_names
        assert "AUTHORIZED_HOST" in scope_names
        assert "AUTHORIZED_DOMAIN" in scope_names

        # Verify AuthorizationStatus
        assert AuthorizationStatus.ALLOWED.value == "ALLOWED"
        assert AuthorizationStatus.DENIED.value == "DENIED"
        assert AuthorizationStatus.REQUIRES_AUTHORIZATION.value == "REQUIRES_AUTHORIZATION"

    # ── 2. Secret Redaction ──
    def test_02_secret_redactor_text_and_jwt(self):
        raw_text = "API_KEY=sk-proj-1234567890abcdef and password: supersecretpassword123"
        clean = SecretRedactor.redact_text(raw_text)
        assert "sk-proj" not in clean
        assert "supersecret" not in clean
        assert "[REDACTED_SECRET]" in clean

    def test_03_secret_redactor_http_headers(self):
        headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.e30.t-ID",
            "Cookie": "session_id=abcdef123456",
            "X-API-Key": "secret-key-xyz",
            "Server": "uvicorn",
        }
        clean = SecretRedactor.redact_headers(headers)
        assert clean["Authorization"] == "[REDACTED_SECRET]"
        assert clean["Cookie"] == "[REDACTED_SECRET]"
        assert clean["X-API-Key"] == "[REDACTED_SECRET]"
        assert clean["Content-Type"] == "application/json"
        assert clean["Server"] == "uvicorn"

    # ── 3. DiagnosticBudget ──
    def test_04_diagnostic_budget_step_and_request_limits(self):
        budget = DiagnosticBudget(max_steps=2, max_network_requests=1)
        assert budget.can_step() is True
        assert budget.can_make_network_request() is True

        budget.record_step()
        budget.record_network_request()
        assert budget.can_make_network_request() is False  # Max network requests reached
        assert budget.can_step() is True

        budget.record_step()
        assert budget.can_step() is False  # Max steps reached

    # ── 4. SecurityToolRegistry ──
    def test_05_security_tool_registry_tools_exist(self):
        tools = security_tool_registry.list_tools()
        expected = ["inspect_port", "inspect_process", "resolve_dns", "test_tcp", "test_http", "inspect_logs", "inspect_routes"]
        for exp in expected:
            assert exp in tools
            t_def = security_tool_registry.get_tool(exp)
            assert t_def is not None
            assert t_def.capability.startswith("security.")

    # ── 5. Port Inspection & Process Correlation ──
    def test_06_port_inspection_and_process_correlation(self):
        skill = CybersecuritySkill()
        state = ComputerState()
        with patch.object(security_tool_registry.get_tool("inspect_port"), "handler", return_value={
            "success": True,
            "port": 8000,
            "is_listening": True,
            "sockets": [{"port": 8000, "pid": 15568, "process_name": "uvicorn", "status": "LISTENING"}]
        }):
            res = skill.execute("port_check", "security", {"port": 8000}, state)
            assert res["success"] is True
            assert res["is_open"] is True
            assert res["pid"] == 15568
            assert res["process_name"] == "uvicorn"

    # ── 6. DNS Diagnostics ──
    def test_07_dns_diagnostics_resolution(self):
        with patch("socket.getaddrinfo", return_value=[(2, 1, 0, "", ("93.184.216.34", 0))]):
            tool = security_tool_registry.get_tool("resolve_dns")
            res = tool.handler(hostname="example.com")
            assert res["success"] is True
            assert res["resolves"] is True
            assert "93.184.216.34" in res["resolved_ips"]

    # ── 7. TCP Diagnostics ──
    def test_08_tcp_diagnostics_handshake(self):
        tool = security_tool_registry.get_tool("test_tcp")
        with patch("socket.socket") as mock_sock_cls:
            mock_s = MagicMock()
            mock_s.connect_ex.return_value = 0
            mock_sock_cls.return_value.__enter__.return_value = mock_s

            res = tool.handler(host="127.0.0.1", port=8000, timeout=1.0)
            assert res["success"] is True
            assert res["connected"] is True

    # ── 8. HTTP Diagnostics with Redacted Headers ──
    def test_09_http_diagnostics_and_header_redaction(self):
        tool = security_tool_registry.get_tool("test_http")
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.headers = {
            "Content-Type": "text/html",
            "Set-Cookie": "auth_token=supersecret123; HttpOnly",
            "Server": "gunicorn",
        }
        mock_resp.__enter__.return_value = mock_resp
        mock_resp.__exit__.return_value = None
        with patch("urllib.request.urlopen", return_value=mock_resp):
            res = tool.handler(url="http://127.0.0.1:8000")
            assert res["success"] is True
            assert res["status_code"] == 200
            assert res["headers"]["Set-Cookie"] == "[REDACTED_SECRET]"
            assert res["headers"]["Server"] == "gunicorn"

    # ── 9. Log Inspection ──
    def test_10_log_inspection_with_error_query(self):
        tool = security_tool_registry.get_tool("inspect_logs")
        mock_file = MagicMock()
        mock_file.name = "server.log"
        mock_file.read_text.return_value = "INFO: Server started\nERROR: Connection refused to db with password: pass123\nINFO: retry\n"

        res = tool.handler(query="error", max_lines=5, files=[mock_file])
        assert res["success"] is True
        assert res["match_count"] == 1
        assert "pass123" not in res["matches"][0]["line"]
        assert "[REDACTED_SECRET]" in res["matches"][0]["line"]

    # ── 10. Route / Network Interface Inspector ──
    def test_11_route_and_interface_inspection(self):
        tool = security_tool_registry.get_tool("inspect_routes")
        with patch("psutil.net_if_addrs") as mock_addrs, patch("psutil.net_if_stats") as mock_stats:
            mock_addr = MagicMock()
            mock_addr.family = 2  # AF_INET
            mock_addr.address = "192.168.1.50"
            mock_addrs.return_value = {"Ethernet": [mock_addr]}

            mock_stat = MagicMock()
            mock_stat.isup = True
            mock_stats.return_value = {"Ethernet": mock_stat}

            res = tool.handler()
            assert res["success"] is True
            assert "Ethernet" in res["interfaces"]
            assert res["interfaces"]["Ethernet"]["is_up"] is True
            assert "192.168.1.50" in res["interfaces"]["Ethernet"]["ipv4_addresses"]

    # ── 11. Adaptive Security Workflow ──
    def test_12_adaptive_workflow_unreachable_server_progression(self):
        # Scenario: HTTP fails -> Port not listening -> Reports port closed
        with patch.object(security_tool_registry.get_tool("test_http"), "handler", return_value={"is_reachable": False, "error": "Connection refused"}), \
             patch.object(security_tool_registry.get_tool("inspect_port"), "handler", return_value={"is_listening": False}):
            ok, summary, evidence = security_workflow.run_investigation("Why can't localhost:8000 connect?")
            assert ok is True
            assert "No process is listening on port 8000" in summary
            assert len(evidence) >= 1

    # ── 12. Scope Enforcement & Unauthorized Target Denial ──
    def test_13_unauthorized_target_scope_denial(self):
        ok, summary, evidence = security_workflow.run_investigation("Scan random-unauthorized-target.evil.com")
        assert ok is False
        assert "outside authorized" in summary
        assert evidence[0].authorization == AuthorizationStatus.DENIED

    # ── 13. Command Injection Prevention ──
    def test_14_command_injection_attempt_rejected(self):
        tool = security_tool_registry.get_tool("resolve_dns")
        res = tool.handler(hostname="google.com; rm -rf /")
        assert res["success"] is False
        assert "Invalid hostname" in res["error"]

    # ── 14. ActionSelector Routing ──
    def test_15_action_selector_routes_security_intents(self):
        state = ComputerState()
        res_port = action_selector.select_action("What's listening on port 8000?", state)
        assert res_port.method == ControlMethod.APPLICATION_SKILL
        assert res_port.target_app == "security"
        assert res_port.action_name == "diagnose"

        res_unreach = action_selector.select_action("Check why my local server isn't reachable", state)
        assert res_unreach.method == ControlMethod.APPLICATION_SKILL
        assert res_unreach.target_app == "security"

    # ── 15. OperatorEngine Integration ──
    @pytest.mark.asyncio
    async def test_16_operator_engine_security_investigation(self):
        from app.services.automation.operator.security.investigation_engine import security_investigation_engine
        with patch.object(security_investigation_engine, "investigate", return_value=(True, "Port 8000 is listening under Uvicorn (PID 15568).", [])):
            resp = await operator_engine.run_operation("What's listening on port 8000?")
            assert resp == "Port 8000 is listening under Uvicorn (PID 15568)."

    # ── 16. Cancellation Safety ──
    def test_17_security_workflow_budget_cancellation(self):
        budget = DiagnosticBudget(max_steps=0)  # Exhausted budget
        ok, summary, ev = security_workflow.run_investigation("What's listening on port 8000?", budget=budget)
        assert ok is False
        assert "budget exceeded" in summary
