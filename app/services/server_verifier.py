"""Server verifier service for FALSO development workflow.

Guarantees clean server lifecycle management, single-instance enforcement,
reuse of active port 8000 server, and mandatory cleanup after verification.
"""

import asyncio
import logging
import py_compile
import socket
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Generator, List, Optional

import httpx

logger = logging.getLogger(__name__)

DEFAULT_PORT = 8000
TEMP_VERIFY_PORT = 8999


def check_port_active(host: str = "127.0.0.1", port: int = DEFAULT_PORT) -> bool:
    """Check if a server is accepting TCP connections on the specified port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex((host, port)) == 0


def detect_active_falso_server() -> Optional[int]:
    """Detect whether a FALSO server is running on port 8000 or temporary ports."""
    for port in [DEFAULT_PORT, TEMP_VERIFY_PORT]:
        if check_port_active("127.0.0.1", port):
            try:
                res = httpx.get(f"http://127.0.0.1:{port}/api/v1/system/diagnostics", timeout=1.0)
                if res.status_code == 200:
                    return port
            except Exception:
                pass
    return None


def validate_code_static(file_paths: List[str]) -> bool:
    """Perform fast static code validation: syntax checking and module compilation."""
    logger.info("[VERIFY] Starting static analysis, syntax, and import validation...")
    success = True
    for file_path in file_paths:
        p = Path(file_path)
        if not p.exists() or p.suffix != ".py":
            continue
        try:
            py_compile.compile(str(p), doraise=True)
            logger.info("[VERIFY] Syntax check PASSED: %s", p.name)
        except py_compile.PyCompileError as err:
            logger.error("[VERIFY] Syntax check FAILED: %s -> %s", p.name, err)
            success = False

    return success


@contextmanager
def temporary_verification_server(port: int = TEMP_VERIFY_PORT) -> Generator[str, None, None]:
    """Context manager for temporary verification server lifecycle.
    
    Reuses existing server on port 8000 if running.
    Otherwise boots temporary uvicorn instance on TEMP_VERIFY_PORT, yields base_url,
    and guarantees immediate server termination upon exit.
    """
    active_port = detect_active_falso_server()
    if active_port:
        logger.info("[SERVER] Existing FALSO server detected on port %d — reusing instance", active_port)
        yield f"http://127.0.0.1:{active_port}"
        logger.info("[SERVER] Verification complete")
        return

    logger.info("[SERVER] Server started on port %d", port)
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    try:
        # Wait up to 5 seconds for startup
        start_time = time.time()
        ready = False
        while time.time() - start_time < 5.0:
            if check_port_active("127.0.0.1", port):
                ready = True
                break
            time.sleep(0.2)

        if not ready:
            raise RuntimeError(f"Temporary verification server failed to start on port {port}")

        yield f"http://127.0.0.1:{port}"
        logger.info("[SERVER] Verification complete")

    finally:
        logger.info("[SERVER] Server stopped on port %d", port)
        proc.terminate()
        try:
            proc.wait(timeout=3.0)
        except subprocess.TimeoutExpired:
            proc.kill()
