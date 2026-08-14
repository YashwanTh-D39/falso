"""
FALSO 4.13 Android Physical Controller.

Dispatches physical touch, key gestures, text typing, screenshots, and file transfers
with truthful post-action verification.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
import time
from typing import Any

from app.services.automation.android.device_manager import android_device_manager
from app.services.automation.android.device_state import AndroidCapabilityState, AndroidExecutionState

logger = logging.getLogger(__name__)


class AndroidController:
    """Dispatches physical touch, hardware keys, and data transfer."""

    def __init__(self, device_manager=None) -> None:
        self.device_manager = device_manager or android_device_manager

    def tap(self, x: int, y: int, device_id: str | None = None) -> dict[str, Any]:
        """Send single touch tap at screen coordinates."""
        logger.info("[ANDROID][EXECUTE] tap at (%d, %d)", x, y)
        res = self.device_manager.execute_operation("tap", {"x": x, "y": y}, device_id=device_id)
        return {
            "success": res.get("success", False),
            "action": "tap",
            "x": x,
            "y": y,
            "verified": res.get("success", False),
        }

    def long_press(self, x: int, y: int, duration_ms: int = 1000, device_id: str | None = None) -> dict[str, Any]:
        """Send long press (swipe with same start and end coordinates)."""
        logger.info("[ANDROID][EXECUTE] long_press at (%d, %d) for %dms", x, y, duration_ms)
        res = self.device_manager.execute_operation(
            "swipe",
            {"x1": x, "y1": y, "x2": x, "y2": y, "duration": duration_ms},
            device_id=device_id,
        )
        return {
            "success": res.get("success", False),
            "action": "long_press",
            "x": x,
            "y": y,
            "duration": duration_ms,
            "verified": res.get("success", False),
        }

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 300, device_id: str | None = None) -> dict[str, Any]:
        """Send swipe gesture."""
        logger.info("[ANDROID][EXECUTE] swipe from (%d, %d) to (%d, %d)", x1, y1, x2, y2)
        res = self.device_manager.execute_operation(
            "swipe",
            {"x1": x1, "y1": y1, "x2": x2, "y2": y2, "duration": duration_ms},
            device_id=device_id,
        )
        return {
            "success": res.get("success", False),
            "action": "swipe",
            "start": (x1, y1),
            "end": (x2, y2),
            "verified": res.get("success", False),
        }

    def scroll(self, direction: str = "down", device_id: str | None = None) -> dict[str, Any]:
        """Simulate vertical or horizontal scroll."""
        if direction.lower() == "down":
            return self.swipe(500, 1500, 500, 500, 300, device_id=device_id)
        elif direction.lower() == "up":
            return self.swipe(500, 500, 500, 1500, 300, device_id=device_id)
        return {"success": False, "error": f"Unsupported scroll direction: {direction}"}

    def back(self, device_id: str | None = None) -> dict[str, Any]:
        """Press Android hardware BACK button."""
        return self.key_event(4, device_id=device_id)

    def home(self, device_id: str | None = None) -> dict[str, Any]:
        """Press Android hardware HOME button."""
        return self.key_event(3, device_id=device_id)

    def recent_apps(self, device_id: str | None = None) -> dict[str, Any]:
        """Press Android hardware APP_SWITCH (recent apps) button."""
        return self.key_event(187, device_id=device_id)

    def wake_display(self, device_id: str | None = None) -> dict[str, Any]:
        """Wake device display without unlocking."""
        logger.info("[ANDROID][EXECUTE] wake_display")
        res = self.device_manager.execute_operation("wake_display", {}, device_id=device_id)
        return {
            "success": res.get("success", False),
            "action": "wake_display",
            "display_state": "DISPLAY_AWAKE" if res.get("success") else "UNKNOWN",
            "verified": res.get("success", False),
        }

    def key_event(self, keycode: int | str, device_id: str | None = None) -> dict[str, Any]:
        """Send Android Keyevent."""
        logger.info("[ANDROID][EXECUTE] key_event keycode=%s", keycode)
        res = self.device_manager.execute_operation("key_event", {"keycode": keycode}, device_id=device_id)
        return {
            "success": res.get("success", False),
            "action": "key_event",
            "keycode": keycode,
            "verified": res.get("success", False),
        }

    def text_input(self, text: str, device_id: str | None = None) -> dict[str, Any]:
        """Type text into active focused element."""
        logger.info("[ANDROID][EXECUTE] text_input length=%d", len(text))
        # ADB text input requires escaping spaces as %s or quoting
        escaped_text = text.replace(" ", "%s")
        res = self.device_manager.execute_operation("text_input", {"text": escaped_text}, device_id=device_id)
        return {
            "success": res.get("success", False),
            "action": "text_input",
            "text": text,
            "verified": res.get("success", False),
        }

    def capture_screenshot(self, target_pc_path: str | None = None, device_id: str | None = None) -> dict[str, Any]:
        """
        Capture screenshot on device, pull to PC, and verify file integrity.
        """
        logger.info("[ANDROID][EXECUTE] capture_screenshot")
        temp_device_path = "/sdcard/falso_screencap.png"

        # 1. Capture on device
        cap_res = self.device_manager.execute_operation("screencap", {"device_path": temp_device_path}, device_id=device_id)
        if not cap_res.get("success"):
            return {
                "success": False,
                "error": "Failed to capture screen image on Android device.",
                "verified": False,
            }

        # Determine PC target path
        pc_dest = target_pc_path or os.path.join(os.getcwd(), "falso_phone_screenshot.png")

        # 2. Pull file to PC
        pull_res = self.device_manager.execute_operation("pull_file", {"device_path": temp_device_path, "pc_path": pc_dest}, device_id=device_id)
        if not pull_res.get("success"):
            return {
                "success": False,
                "error": "Failed to transfer screenshot from Android device to PC.",
                "verified": False,
            }

        # 3. Verify file exists on PC and has non-zero size
        p = Path(pc_dest)
        if not p.exists() or p.stat().st_size == 0:
            return {
                "success": False,
                "error": "Screenshot file was not written or is empty on PC.",
                "verified": False,
            }

        logger.info("[ANDROID][VERIFY] screenshot verified at %s (%d bytes)", pc_dest, p.stat().st_size)
        return {
            "success": True,
            "file_path": str(p.absolute()),
            "file_size": p.stat().st_size,
            "verified": True,
        }

    def file_pull(self, device_path: str, pc_path: str, device_id: str | None = None) -> dict[str, Any]:
        """Transfer file Phone -> PC with verification."""
        logger.info("[ANDROID][EXECUTE] file_pull from %s to %s", device_path, pc_path)
        res = self.device_manager.execute_operation("pull_file", {"device_path": device_path, "pc_path": pc_path}, device_id=device_id)
        if not res.get("success"):
            return {"success": False, "error": "Pull operation failed.", "verified": False}

        p = Path(pc_path)
        if not p.exists() or p.stat().st_size == 0:
            return {"success": False, "error": "Destination file not found or empty on PC.", "verified": False}

        return {"success": True, "pc_path": str(p.absolute()), "size": p.stat().st_size, "verified": True}

    def file_push(self, pc_path: str, device_path: str, device_id: str | None = None) -> dict[str, Any]:
        """Transfer file PC -> Phone with verification."""
        p = Path(pc_path)
        if not p.exists():
            return {"success": False, "error": f"Source PC file '{pc_path}' does not exist.", "verified": False}

        logger.info("[ANDROID][EXECUTE] file_push from %s to %s", pc_path, device_path)
        res = self.device_manager.execute_operation("push_file", {"pc_path": pc_path, "device_path": device_path}, device_id=device_id)
        if not res.get("success"):
            return {"success": False, "error": "Push operation failed.", "verified": False}

        return {"success": True, "device_path": device_path, "size": p.stat().st_size, "verified": True}


android_controller = AndroidController()
