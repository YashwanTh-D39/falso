"""
Windows Process Manager Service for FALSO.

Manages application process detection, approved launches, and process verification.
Integrated with PermissionManager Application Allowlist.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
import subprocess
import time
from typing import Any

import psutil

from app.services.automation.permissions import permission_manager
from app.services.automation.windows.window_manager import window_manager

logger = logging.getLogger(__name__)

# Map common application aliases to standard Windows executables
APP_EXECUTABLE_MAP: dict[str, str] = {
    "calculator": "calc.exe",
    "calc": "calc.exe",
    "calc.exe": "calc.exe",
    "notepad": "notepad.exe",
    "notepad.exe": "notepad.exe",
    "chrome": "chrome.exe",
    "chrome.exe": "chrome.exe",
    "msedge": "msedge.exe",
    "msedge.exe": "msedge.exe",
    "edge": "msedge.exe",
    "file explorer": "explorer.exe",
    "explorer": "explorer.exe",
    "explorer.exe": "explorer.exe",
    "vs code": "code.cmd",
    "vscode": "code.cmd",
    "code": "code.cmd",
    "code.exe": "code.cmd",
    "terminal": "wt.exe",
    "wt": "wt.exe",
    "cmd": "cmd.exe",
    "command prompt": "cmd.exe",
    "powershell": "powershell.exe",
}


class ProcessManager:
    """Safe Windows Process & Application Launch Manager."""

    def is_process_running(self, process_name: str) -> bool:
        """Check if process matching process_name is currently active."""
        name_clean = process_name.lower().replace(".exe", "").replace(".cmd", "")
        if name_clean in ("calculator", "calc", "calculatorapp"):
            targets = ("calc", "calculator", "calculatorapp")
        else:
            targets = (name_clean,)

        try:
            for proc in psutil.process_iter(['name']):
                pname = (proc.info.get('name') or "").lower().replace(".exe", "")
                if any(t in pname for t in targets):
                    return True
        except Exception as e:
            logger.warning("[PROCESS_MANAGER] Error checking process: %s", e)
        return False

    def launch_app(self, app_name: str, args: list[str] | None = None) -> dict[str, Any]:
        """Launch an approved application or focus it if already running, returning verified Action Truth."""
        from app.services.automation.windows.app_registry import app_registry

        app_info = app_registry.resolve(app_name)
        canonical = app_info.canonical_name if app_info else app_name.title()
        clean_app = app_name.lower().strip()

        # Check PermissionManager allowlist
        perm = permission_manager.check_application_launch(clean_app)
        if not perm.allowed:
            logger.warning("[PROCESS_MANAGER] Launch DENIED for '%s': %s", app_name, perm.reason)
            return {
                "success": False,
                "action": "launch_app",
                "target": canonical,
                "executed": False,
                "verified": False,
                "verification_reason": f"Permission denied for {canonical}: {perm.reason}",
            }

        # If window is already open, focus existing window
        if window_manager.is_window_open(clean_app) or window_manager.focus_window(clean_app):
            logger.info("[PROCESS_MANAGER] Application '%s' already open — Focused existing window.", canonical)
            return {
                "success": True,
                "action": "launch_app",
                "target": canonical,
                "executed": True,
                "verified": True,
                "verification_reason": f"{canonical} is open.",
            }

        try:
            if clean_app in ("calculator", "calc", "calc.exe"):
                subprocess.Popen(["calc.exe"])
            elif clean_app in ("chrome", "chrome.exe", "google chrome"):
                chrome_paths = [
                    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
                    os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
                ]
                chrome_exe = next((p for p in chrome_paths if os.path.exists(p)), None)
                if chrome_exe:
                    subprocess.Popen([chrome_exe] + (args or []))
                    logger.info("[PROCESS_MANAGER] Launched Chrome executable: %s", chrome_exe)
                else:
                    url = args[0] if args else "http://localhost:8000"
                    import webbrowser
                    webbrowser.open(url)
            elif clean_app in ("claude", "claude.exe", "claude desktop", "anthropic claude"):
                claude_paths = app_info.executable_paths if app_info else []
                claude_exe = next((p for p in claude_paths if os.path.exists(p)), None)
                if claude_exe:
                    subprocess.Popen([claude_exe] + (args or []))
                    logger.info("[PROCESS_MANAGER] Launched Claude executable: %s", claude_exe)
                else:
                    import webbrowser
                    webbrowser.open("https://claude.ai")
                    logger.info("[PROCESS_MANAGER] Opened Claude web app via default browser.")
            elif clean_app in ("msedge", "msedge.exe", "edge", "browser"):
                url = args[0] if args else "http://localhost:8000"
                import webbrowser
                webbrowser.open(url)
            elif clean_app in ("vs code", "vscode", "code", "code.exe"):
                vscode_path = os.path.expandvars(r"%LOCALAPPDATA%\Programs\Microsoft VS Code\Code.exe")
                if os.path.exists(vscode_path):
                    subprocess.Popen([vscode_path] + (args or []))
                else:
                    subprocess.Popen("start code", shell=True)
            else:
                executable = APP_EXECUTABLE_MAP.get(clean_app, f"{clean_app}.exe")
                cmd_str = f"start {executable}"
                if args:
                    cmd_str += " " + " ".join(args)
                subprocess.Popen(cmd_str, shell=True)

            # Event-driven wait for window readiness
            found = window_manager.wait_for_window(clean_app, timeout=3.0)
            if found or window_manager.is_window_open(clean_app):
                logger.info("[AUTOMATION][VERIFY_RESULT] target=%s expected=open actual=open result=PASS", canonical)
                return {
                    "success": True,
                    "action": "launch_app",
                    "target": canonical,
                    "executed": True,
                    "verified": True,
                    "verification_reason": f"{canonical} is open.",
                }
            else:
                logger.warning("[AUTOMATION][VERIFY_RESULT] target=%s expected=open actual=absent result=FAIL", canonical)
                return {
                    "success": False,
                    "action": "launch_app",
                    "target": canonical,
                    "executed": True,
                    "verified": False,
                    "verification_reason": f"I couldn't open {canonical}.",
                }
        except Exception as e:
            logger.exception("[PROCESS_MANAGER] Failed to launch '%s': %s", app_name, e)
            return {
                "success": False,
                "action": "launch_app",
                "target": canonical,
                "executed": False,
                "verified": False,
                "verification_reason": f"I couldn't open {canonical}.",
            }

    def stop_process(self, process_name: str) -> bool:
        """Stop an approved application process."""
        name_clean = process_name.lower().replace(".exe", "")
        # Protect system processes
        if name_clean in ("csrss", "lsass", "smss", "services", "svchost", "winlogon", "system"):
            logger.warning("[PROCESS_MANAGER] Terminating system process '%s' is DENIED.", process_name)
            return False

        stopped = False
        try:
            for proc in psutil.process_iter(['name', 'pid']):
                pname = (proc.info.get('name') or "").lower().replace(".exe", "")
                if name_clean == pname:
                    proc.terminate()
                    stopped = True
        except Exception as e:
            logger.warning("[PROCESS_MANAGER] Error terminating process: %s", e)
        return stopped


process_manager = ProcessManager()
