"""
Windows Mouse Controller Service for FALSO.

Uses native Win32 API via ctypes to execute mouse movements, clicks, and scrolling.
Coordinates are used as LAST RESORT when structured UI element targeting is unavailable.
"""

from __future__ import annotations

import ctypes
import logging
import time

logger = logging.getLogger(__name__)

user32 = ctypes.windll.user32

# Win32 Mouse Event Flags
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040
MOUSEEVENTF_WHEEL = 0x0800


class MouseController:
    """Native Win32 Mouse Controller."""

    def get_position(self) -> tuple[int, int]:
        """Get current mouse cursor position (x, y)."""
        point = ctypes.wintypes.POINT()
        user32.GetCursorPos(ctypes.byref(point))
        return point.x, point.y

    def move_to(self, x: int, y: int) -> bool:
        """Move cursor to (x, y) coordinates."""
        user32.SetCursorPos(x, y)
        logger.debug("[MOUSE] Moved cursor to (%d, %d)", x, y)
        return True

    def click(self, x: int | None = None, y: int | None = None, button: str = "left") -> bool:
        """Click mouse button at specified (x, y) or current location."""
        if x is not None and y is not None:
            self.move_to(x, y)
        time.sleep(0.02)

        if button == "right":
            user32.mouse_event(MOUSEEVENTF_RIGHTDOWN, 0, 0, 0, 0)
            time.sleep(0.02)
            user32.mouse_event(MOUSEEVENTF_RIGHTUP, 0, 0, 0, 0)
        else:
            user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
            time.sleep(0.02)
            user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)

        logger.info("[MOUSE] %s click at (%d, %d)", button.capitalize(), x or 0, y or 0)
        return True

    def double_click(self, x: int | None = None, y: int | None = None) -> bool:
        """Perform rapid double click."""
        self.click(x, y)
        time.sleep(0.05)
        self.click(x, y)
        return True

    def scroll(self, clicks: int = -3) -> bool:
        """Scroll mouse wheel (negative = down, positive = up)."""
        user32.mouse_event(MOUSEEVENTF_WHEEL, 0, 0, clicks * 120, 0)
        logger.debug("[MOUSE] Scrolled mouse wheel (%d clicks)", clicks)
        return True


mouse_controller = MouseController()
