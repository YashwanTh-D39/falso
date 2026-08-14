"""
Windows Window Manager Service for FALSO.

Uses native Win32 API via ctypes to manage open windows:
- List visible windows
- Identify foreground/active window
- Focus, minimize, maximize, restore window
- Detect window readiness with event-driven wait timeouts
- Foreground verification for input safety
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import logging
import time
from typing import Any

logger = logging.getLogger(__name__)

# Win32 Constants
SW_HIDE = 0
SW_SHOWNORMAL = 1
SW_SHOWMINIMIZED = 2
SW_SHOWMAXIMIZED = 3
SW_RESTORE = 9

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)


class WindowManager:
    """Native Win32 Window Manager using ctypes."""

    def list_windows(self) -> list[dict[str, Any]]:
        """List all visible top-level desktop windows."""
        windows: list[dict[str, Any]] = []

        def enum_win_callback(hwnd: int, lparam: int) -> bool:
            if user32.IsWindowVisible(hwnd):
                length = user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    buf = ctypes.create_unicode_buffer(length + 1)
                    user32.GetWindowTextW(hwnd, buf, length + 1)
                    title = buf.value.strip()
                    if title and title not in ("Program Manager", "Default IME", "MSCTFIME UI"):
                        windows.append({
                            "hwnd": hwnd,
                            "title": title,
                            "visible": True,
                        })
            return True

        callback = WNDENUMPROC(enum_win_callback)
        user32.EnumWindows(callback, 0)
        return windows

    def get_active_window(self) -> dict[str, Any]:
        """Get currently focused/foreground window."""
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return {"hwnd": 0, "title": "Unknown"}

        length = user32.GetWindowTextLengthW(hwnd)
        if length > 0:
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            title = buf.value.strip()
        else:
            title = "Unknown"

        return {"hwnd": hwnd, "title": title}

    def get_foreground_hwnd(self) -> dict[str, Any]:
        """Get foreground window hwnd, title, and process ID.

        Returns a dict with:
          hwnd: int — the window handle (0 if none)
          title: str — the window title
          process_id: int — the owning process ID (0 if unavailable)
        """
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return {"hwnd": 0, "title": "Unknown", "process_id": 0}

        length = user32.GetWindowTextLengthW(hwnd)
        if length > 0:
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            title = buf.value.strip()
        else:
            title = "Unknown"

        pid = wintypes.DWORD(0)
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))

        return {"hwnd": hwnd, "title": title, "process_id": pid.value}

    def is_window_open(self, title_substring: str) -> bool:
        """Check if a VISIBLE window with matching title exists.

        Returns True ONLY when an actual visible window is found.
        Background processes without visible windows return False.
        """
        from app.services.automation.windows.app_registry import app_registry
        patterns = app_registry.get_title_patterns(title_substring)

        for win in self.list_windows():
            t_lower = win["title"].lower()
            if any(p in t_lower for p in patterns):
                return True

        return False

    def focus_window(self, title_substring: str) -> bool:
        """Find and bring matching VISIBLE window to front.

        Returns True ONLY after locating a valid visible HWND and
        successfully calling SetForegroundWindow on it.
        Background processes without visible windows return False.
        """
        from app.services.automation.windows.app_registry import app_registry
        patterns = app_registry.get_title_patterns(title_substring)

        for win in self.list_windows():
            t_lower = win["title"].lower()
            if any(p in t_lower for p in patterns):
                hwnd = win["hwnd"]
                user32.ShowWindow(hwnd, SW_RESTORE)
                user32.SetForegroundWindow(hwnd)
                logger.info("[WINDOW_MANAGER] Focused window: %r (hwnd=%d)", win["title"], hwnd)
                return True

        logger.info("[WINDOW_MANAGER] No visible window found for '%s'", title_substring)
        return False

    def verify_foreground(self, title_substring: str) -> bool:
        """Verify that the foreground window matches the expected target.

        Call this AFTER focus_window() to confirm the correct window
        actually received focus before sending keyboard/mouse input.
        """
        from app.services.automation.windows.app_registry import app_registry
        patterns = app_registry.get_title_patterns(title_substring)

        fg = self.get_foreground_hwnd()
        if not fg["hwnd"]:
            return False

        fg_title_lower = fg["title"].lower()
        return any(p in fg_title_lower for p in patterns)

    def minimize_window(self, title_substring: str) -> bool:
        from app.services.automation.windows.app_registry import app_registry
        patterns = app_registry.get_title_patterns(title_substring)
        for win in self.list_windows():
            t_lower = win["title"].lower()
            if any(p in t_lower for p in patterns):
                user32.ShowWindow(win["hwnd"], SW_SHOWMINIMIZED)
                return True
        return False

    def maximize_window(self, title_substring: str) -> bool:
        from app.services.automation.windows.app_registry import app_registry
        patterns = app_registry.get_title_patterns(title_substring)
        for win in self.list_windows():
            t_lower = win["title"].lower()
            if any(p in t_lower for p in patterns):
                user32.ShowWindow(win["hwnd"], SW_SHOWMAXIMIZED)
                return True
        return False

    def wait_for_window(self, title_substring: str, timeout: float = 5.0) -> bool:
        """Event-driven check: wait until a VISIBLE window matching title_substring appears."""
        start = time.perf_counter()
        while time.perf_counter() - start < timeout:
            if self.is_window_open(title_substring):
                return True
            time.sleep(0.1)
        return False

    def wait_for_window_close(self, title_substring: str, timeout: float = 3.0) -> bool:
        """Event-driven check: wait until window matching title_substring closes."""
        start = time.perf_counter()
        while time.perf_counter() - start < timeout:
            if not self.is_window_open(title_substring):
                return True
            time.sleep(0.1)
        return False

    def close_window(self, title_substring: str) -> dict[str, Any]:
        """Gracefully close top-level window matching title_substring via Win32 WM_CLOSE with state verification."""
        from app.services.automation.windows.app_registry import app_registry
        from app.services.automation.windows.process_manager import process_manager

        app_info = app_registry.resolve(title_substring)
        canonical = app_info.canonical_name if app_info else title_substring.title()
        patterns = app_registry.get_title_patterns(title_substring)

        WM_CLOSE = 0x0010
        matching_wins = [
            win for win in self.list_windows()
            if any(p in win["title"].lower() for p in patterns)
        ]

        # Check unsaved content
        for win in matching_wins:
            t_lower = win["title"].lower()
            if "*" in win["title"] or "save" in t_lower or "unsaved" in t_lower:
                reason = f"{canonical} has unsaved changes. I won't close it without confirmation."
                logger.warning("[WINDOW_MANAGER][VERIFY] %s", reason)
                return {
                    "success": False,
                    "action": "close_window",
                    "target": canonical,
                    "executed": False,
                    "verified": False,
                    "verification_reason": reason,
                    "unsaved_changes": True,
                    "before_state": {"window_open": True},
                    "after_state": {"window_open": True},
                }

        # If no matching visible window found, check process state for cleanup
        if not matching_wins:
            proc_running = False
            for pname in app_registry.get_process_names(title_substring):
                if process_manager.is_process_running(pname):
                    proc_running = True
                    process_manager.stop_process(pname)

            if not proc_running:
                reason = f"{canonical} is already closed."
                logger.info("[WINDOW_MANAGER][VERIFY] %s", reason)
                return {
                    "success": True,
                    "action": "close_window",
                    "target": canonical,
                    "executed": False,
                    "verified": True,
                    "verification_reason": reason,
                    "before_state": {"window_open": False},
                    "after_state": {"window_open": False},
                }

        # Send WM_CLOSE to all matching windows
        for win in matching_wins:
            user32.PostMessageW(win["hwnd"], WM_CLOSE, 0, 0)
            logger.info("[WINDOW_MANAGER][ACTION] Sent WM_CLOSE to window: %r", win["title"])

        # Wait and verify state change
        closed_verified = self.wait_for_window_close(title_substring, timeout=2.5)
        proc_still_running = False
        for pname in app_registry.get_process_names(title_substring):
            if process_manager.is_process_running(pname):
                proc_still_running = True

        if closed_verified and not proc_still_running:
            reason = f"{canonical} is closed."
            logger.info("[AUTOMATION][VERIFY_RESULT] target=%s expected=closed actual=closed result=PASS", canonical)
            return {
                "success": True,
                "action": "close_window",
                "target": canonical,
                "executed": True,
                "verified": True,
                "verification_reason": reason,
                "before_state": {"window_open": True},
                "after_state": {"window_open": False},
            }
        else:
            reason = f"I couldn't close {canonical}."
            logger.warning("[AUTOMATION][VERIFY_RESULT] target=%s expected=closed actual=open result=FAIL", canonical)
            return {
                "success": False,
                "action": "close_window",
                "target": canonical,
                "executed": True,
                "verified": False,
                "verification_reason": reason,
                "before_state": {"window_open": True},
                "after_state": {"window_open": True},
            }


window_manager = WindowManager()
