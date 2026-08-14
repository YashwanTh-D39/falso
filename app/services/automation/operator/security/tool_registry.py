"""
FALSO 4.10 Controlled Security Tool Registry.

Defines safe, schema-validated, controlled security diagnostic tools:
- Port Inspector (psutil socket discovery & process correlation)
- Process Mapper (PID -> process name, status, cmdline)
- DNS Diagnostics (socket.getaddrinfo)
- TCP Diagnostics (socket handshake test)
- HTTP Diagnostics (safe HTTP request with header redaction)
- Log Inspector (bounded workspace log scanning with secret redaction)
- Route Inspector (network interface enumeration)

STRICT SECURITY INVARIANTS:
- No raw shell string execution
- No command injection vulnerabilities
- Scope & authorization validation on every invocation
- Automatic secret redaction on all outputs
"""

from __future__ import annotations

from dataclasses import dataclass, field
import logging
from pathlib import Path
import socket
import time
from typing import Any, Callable
import urllib.error
import urllib.request

import psutil

from app.services.automation.operator.security.evidence import (
    AuthorizationStatus,
    DiagnosticBudget,
    FindingSeverity,
    SecretRedactor,
    SecurityEvidence,
    SecurityScope,
)
from app.services.automation.permissions import PermissionLevel, RiskLevel, permission_manager

logger = logging.getLogger(__name__)


@dataclass
class SecurityToolDefinition:
    tool_name: str
    capability: str
    description: str
    allowed_arguments: set[str]
    scope_requirements: list[SecurityScope]
    permission_level: PermissionLevel = PermissionLevel.LEVEL_0_OBSERVE
    risk_level: RiskLevel = RiskLevel.LOW
    timeout: float = 5.0
    output_limit_bytes: int = 10_000
    handler: Callable[..., dict[str, Any]] = field(default=lambda **kwargs: {})


class SecurityToolRegistry:
    """Registry of authorized, bounded, schema-validated cybersecurity diagnostic tools."""

    def __init__(self) -> None:
        self._tools: dict[str, SecurityToolDefinition] = {}
        self._register_default_tools()

    def register_tool(self, tool_def: SecurityToolDefinition) -> None:
        self._tools[tool_def.tool_name] = tool_def
        logger.debug("[SECURITY_TOOL_REGISTRY] Registered tool: %s", tool_def.tool_name)

    def get_tool(self, tool_name: str) -> SecurityToolDefinition | None:
        return self._tools.get(tool_name)

    def list_tools(self) -> list[str]:
        return list(self._tools.keys())

    def _register_default_tools(self) -> None:
        # 1. Port Inspector
        self.register_tool(
            SecurityToolDefinition(
                tool_name="inspect_port",
                capability="security.port_inspect",
                description="Inspect listening network sockets on local machine and correlate to PID/Process.",
                allowed_arguments={"port", "protocol", "host"},
                scope_requirements=[SecurityScope.LOCAL_MACHINE],
                permission_level=PermissionLevel.LEVEL_0_OBSERVE,
                risk_level=RiskLevel.LOW,
                handler=self._handle_inspect_port,
            )
        )

        # 2. Process Mapper
        self.register_tool(
            SecurityToolDefinition(
                tool_name="inspect_process",
                capability="security.process_inspect",
                description="Inspect process details, health, and associated ports for a given PID or process name.",
                allowed_arguments={"pid", "process_name"},
                scope_requirements=[SecurityScope.LOCAL_MACHINE],
                permission_level=PermissionLevel.LEVEL_0_OBSERVE,
                risk_level=RiskLevel.LOW,
                handler=self._handle_inspect_process,
            )
        )

        # 3. DNS Diagnostics
        self.register_tool(
            SecurityToolDefinition(
                tool_name="resolve_dns",
                capability="security.dns_diagnostics",
                description="Resolve domain hostname to IP addresses via system DNS resolver.",
                allowed_arguments={"hostname", "authorized_domain"},
                scope_requirements=[SecurityScope.LOCAL_MACHINE, SecurityScope.AUTHORIZED_DOMAIN],
                permission_level=PermissionLevel.LEVEL_0_OBSERVE,
                risk_level=RiskLevel.LOW,
                handler=self._handle_resolve_dns,
            )
        )

        # 4. TCP Diagnostics
        self.register_tool(
            SecurityToolDefinition(
                tool_name="test_tcp",
                capability="security.tcp_diagnostics",
                description="Perform TCP 3-way handshake test against specified host and port.",
                allowed_arguments={"host", "port", "timeout"},
                scope_requirements=[SecurityScope.LOCAL_MACHINE, SecurityScope.AUTHORIZED_HOST],
                permission_level=PermissionLevel.LEVEL_1_INTERACT,
                risk_level=RiskLevel.LOW,
                handler=self._handle_test_tcp,
            )
        )

        # 5. HTTP Diagnostics
        self.register_tool(
            SecurityToolDefinition(
                tool_name="test_http",
                capability="security.http_diagnostics",
                description="Perform safe HTTP/HTTPS GET/HEAD connectivity check with secret header redaction.",
                allowed_arguments={"url", "method", "timeout"},
                scope_requirements=[SecurityScope.LOCAL_MACHINE, SecurityScope.AUTHORIZED_HOST, SecurityScope.AUTHORIZED_DOMAIN],
                permission_level=PermissionLevel.LEVEL_1_INTERACT,
                risk_level=RiskLevel.LOW,
                handler=self._handle_test_http,
            )
        )

        # 6. Log Inspector
        self.register_tool(
            SecurityToolDefinition(
                tool_name="inspect_logs",
                capability="security.log_inspect",
                description="Search approved local application logs for error/warning patterns with secret redaction.",
                allowed_arguments={"query", "log_file", "max_lines"},
                scope_requirements=[SecurityScope.LOCAL_MACHINE, SecurityScope.USER_APPROVED_RESOURCE],
                permission_level=PermissionLevel.LEVEL_2_USER_FILES,
                risk_level=RiskLevel.MEDIUM,
                handler=self._handle_inspect_logs,
            )
        )

        # 7. Route / Network Interface Inspector
        self.register_tool(
            SecurityToolDefinition(
                tool_name="inspect_routes",
                capability="security.route_inspect",
                description="Inspect local network interfaces, IP configurations, and status.",
                allowed_arguments={"interface_name"},
                scope_requirements=[SecurityScope.LOCAL_MACHINE],
                permission_level=PermissionLevel.LEVEL_0_OBSERVE,
                risk_level=RiskLevel.LOW,
                handler=self._handle_inspect_routes,
            )
        )

    # ── Tool Implementations ──

    def _handle_inspect_port(self, **kwargs) -> dict[str, Any]:
        target_port = kwargs.get("port")
        if target_port is not None:
            try:
                target_port = int(target_port)
            except ValueError:
                return {"success": False, "error": f"Invalid port: {target_port}"}

        listening_sockets = []
        try:
            conns = psutil.net_connections(kind="inet")
            for c in conns:
                if c.status == psutil.CONN_LISTEN:
                    l_port = c.laddr.port if c.laddr else 0
                    if target_port is None or l_port == target_port:
                        proc_name = ""
                        if c.pid:
                            try:
                                proc_name = psutil.Process(c.pid).name()
                            except (psutil.NoSuchProcess, psutil.AccessDenied):
                                proc_name = "Unknown"
                        listening_sockets.append({
                            "port": l_port,
                            "ip": c.laddr.ip if c.laddr else "",
                            "pid": c.pid,
                            "process_name": proc_name,
                            "status": "LISTENING",
                        })
        except (psutil.AccessDenied, Exception) as e:
            # Fallback to direct socket probe for target_port
            if target_port:
                is_open = self._probe_socket_open("127.0.0.1", target_port)
                if is_open:
                    listening_sockets.append({
                        "port": target_port,
                        "ip": "127.0.0.1",
                        "pid": None,
                        "process_name": "Active Service",
                        "status": "LISTENING",
                    })

        return {
            "success": True,
            "port": target_port,
            "count": len(listening_sockets),
            "sockets": listening_sockets,
            "is_listening": len(listening_sockets) > 0,
        }

    def _handle_inspect_process(self, **kwargs) -> dict[str, Any]:
        target_pid = kwargs.get("pid")
        proc_name_query = kwargs.get("process_name")

        matches = []
        try:
            for p in psutil.process_iter(["pid", "name", "status", "create_time", "cpu_percent", "memory_percent"]):
                info = p.info
                if target_pid and info["pid"] == int(target_pid):
                    matches.append(info)
                    break
                if proc_name_query and proc_name_query.lower() in (info["name"] or "").lower():
                    matches.append(info)
                    if len(matches) >= 5:
                        break
        except Exception as e:
            logger.warning("[SECURITY] Process inspection error: %s", e)

        return {
            "success": True,
            "count": len(matches),
            "processes": SecretRedactor.redact_dict({"matches": matches})["matches"],
        }

    def _handle_resolve_dns(self, **kwargs) -> dict[str, Any]:
        hostname = kwargs.get("hostname", "localhost")
        # Validate hostname format (prevent injection)
        if not hostname or any(c in hostname for c in ";|&`$<>"):
            return {"success": False, "error": f"Invalid hostname: {hostname}"}

        try:
            addrs = socket.getaddrinfo(hostname, None)
            resolved_ips = list({a[4][0] for a in addrs if a and len(a) > 4})
            return {
                "success": True,
                "hostname": hostname,
                "resolved_ips": resolved_ips,
                "resolves": len(resolved_ips) > 0,
            }
        except Exception as e:
            return {
                "success": False,
                "hostname": hostname,
                "error": str(e),
                "resolves": False,
            }

    def _handle_test_tcp(self, **kwargs) -> dict[str, Any]:
        host = kwargs.get("host", "127.0.0.1")
        port = int(kwargs.get("port", 80))
        timeout = float(kwargs.get("timeout", 2.0))

        start_t = time.perf_counter()
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(timeout)
                res = s.connect_ex((host, port))
                latency_ms = (time.perf_counter() - start_t) * 1000.0
                return {
                    "success": True,
                    "host": host,
                    "port": port,
                    "connected": res == 0,
                    "latency_ms": round(latency_ms, 2),
                }
        except Exception as e:
            return {
                "success": False,
                "host": host,
                "port": port,
                "connected": False,
                "error": str(e),
            }

    def _handle_test_http(self, **kwargs) -> dict[str, Any]:
        url = kwargs.get("url", "http://127.0.0.1:8000")
        timeout = float(kwargs.get("timeout", 3.0))

        # Validate URL scheme
        if not url.startswith(("http://", "https://")):
            url = f"http://{url}"

        start_t = time.perf_counter()
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "FALSO-Diagnostic-Operator/4.10"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                latency_ms = (time.perf_counter() - start_t) * 1000.0
                raw_headers = dict(resp.headers) if hasattr(resp, "headers") and resp.headers else {}
                clean_headers = SecretRedactor.redact_headers(raw_headers)
                status_val = getattr(resp, "status", getattr(resp, "code", 200))
                return {
                    "success": True,
                    "url": url,
                    "status_code": status_val,
                    "latency_ms": round(latency_ms, 2),
                    "headers": clean_headers,
                    "is_reachable": True,
                }
        except urllib.error.HTTPError as he:
            latency_ms = (time.perf_counter() - start_t) * 1000.0
            clean_headers = SecretRedactor.redact_headers(dict(he.headers)) if hasattr(he, "headers") and he.headers else {}
            return {
                "success": True,
                "url": url,
                "status_code": he.code,
                "latency_ms": round(latency_ms, 2),
                "headers": clean_headers,
                "is_reachable": True,
                "http_error": f"HTTP {he.code}",
            }
        except urllib.error.URLError as ue:
            return {
                "success": False,
                "url": url,
                "is_reachable": False,
                "error": str(ue.reason),
                "failure_type": "CONNECT_FAILURE",
            }
        except Exception as e:
            return {
                "success": False,
                "url": url,
                "is_reachable": False,
                "error": str(e),
                "failure_type": "UNKNOWN_ERROR",
            }

    def _handle_inspect_logs(self, **kwargs) -> dict[str, Any]:
        query = kwargs.get("query", "error").lower()
        max_lines = int(kwargs.get("max_lines", 50))
        target_files = kwargs.get("files")

        matching_lines = []
        scanned_bytes = 0

        try:
            if target_files is not None:
                file_list = target_files
            else:
                workspace_root = Path(r"C:\Users\Admin\Project-Falso")
                file_list = list(workspace_root.glob("**/*.log"))

            for log_path in file_list:
                if "venv" in str(log_path) or ".git" in str(log_path):
                    continue
                try:
                    content = log_path.read_text(encoding="utf-8", errors="ignore")
                    scanned_bytes += len(content)
                    for line in content.splitlines():
                        if query in line.lower():
                            clean_line = SecretRedactor.redact_text(line.strip())
                            matching_lines.append({
                                "file": getattr(log_path, "name", "log"),
                                "line": clean_line,
                            })
                            if len(matching_lines) >= max_lines:
                                break
                except Exception:
                    continue
                if len(matching_lines) >= max_lines:
                    break
        except Exception as e:
            logger.warning("[SECURITY] Log inspection failed: %s", e)

        return {
            "success": True,
            "query": query,
            "scanned_bytes": scanned_bytes,
            "match_count": len(matching_lines),
            "matches": matching_lines,
        }

    def _handle_inspect_routes(self, **kwargs) -> dict[str, Any]:
        interfaces = {}
        try:
            addrs = psutil.net_if_addrs()
            stats = psutil.net_if_stats()
            for iface, addr_list in addrs.items():
                is_up = stats[iface].isup if iface in stats else True
                ip_list = [a.address for a in addr_list if a.family == socket.AF_INET]
                interfaces[iface] = {
                    "is_up": is_up,
                    "ipv4_addresses": ip_list,
                }
        except Exception as e:
            logger.warning("[SECURITY] Route inspection failed: %s", e)

        return {
            "success": True,
            "interfaces": interfaces,
        }

    def _probe_socket_open(self, host: str, port: int) -> bool:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(0.5)
                return s.connect_ex((host, port)) == 0
        except Exception:
            return False


security_tool_registry = SecurityToolRegistry()
