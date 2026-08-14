"""
FALSO 4.13 ADB Command Allowlist & Operations Registry.

Strictly defines all allowed ADB operations.
Arbitrary shell execution is prohibited.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any, Callable


@dataclass
class AndroidOperation:
    operation_id: str
    command_args: list[str]  # e.g. ["shell", "dumpsys", "battery"]
    permission_category: str
    risk_level: str = "LOW"
    timeout_sec: float = 10.0
    validator: Callable[[dict[str, Any]], bool] | None = None
    description: str = ""


class AndroidOperationRegistry:
    """Allowlist registry for all ADB operations."""

    def __init__(self) -> None:
        self._operations: dict[str, AndroidOperation] = {}
        self._register_default_operations()

    def _register_default_operations(self) -> None:
        # 1. Device Info & Properties
        self.register(
            AndroidOperation(
                operation_id="get_prop",
                command_args=["shell", "getprop", "{prop_name}"],
                permission_category="ANDROID_DEVICE_READ",
                risk_level="LOW",
                timeout_sec=5.0,
                validator=lambda p: bool(re.match(r"^[a-zA-Z0-9_\.]+$", str(p.get("prop_name", "")))),
                description="Get device system property",
            )
        )

        # 2. Battery Status
        self.register(
            AndroidOperation(
                operation_id="get_battery",
                command_args=["shell", "dumpsys", "battery"],
                permission_category="ANDROID_DEVICE_READ",
                risk_level="LOW",
                timeout_sec=5.0,
                description="Read device battery status",
            )
        )

        # 3. Storage Status
        self.register(
            AndroidOperation(
                operation_id="get_storage",
                command_args=["shell", "df", "/data"],
                permission_category="ANDROID_DEVICE_READ",
                risk_level="LOW",
                timeout_sec=5.0,
                description="Read device storage statistics",
            )
        )

        # 4. Window / Foreground Activity
        self.register(
            AndroidOperation(
                operation_id="get_foreground_window",
                command_args=["shell", "dumpsys", "window", "windows"],
                permission_category="ANDROID_DEVICE_READ",
                risk_level="LOW",
                timeout_sec=5.0,
                description="Inspect current focused window and application",
            )
        )
        self.register(
            AndroidOperation(
                operation_id="get_foreground_activity",
                command_args=["shell", "dumpsys", "activity", "activities"],
                permission_category="ANDROID_DEVICE_READ",
                risk_level="LOW",
                timeout_sec=5.0,
                description="Inspect current resumed activity and foreground package",
            )
        )

        # 5. Lock State
        self.register(
            AndroidOperation(
                operation_id="get_lock_state",
                command_args=["shell", "dumpsys", "trust"],
                permission_category="ANDROID_DEVICE_READ",
                risk_level="LOW",
                timeout_sec=5.0,
                description="Inspect trust manager / lock state",
            )
        )

        # 6. Installed Packages
        self.register(
            AndroidOperation(
                operation_id="list_packages",
                command_args=["shell", "pm", "list", "packages"],
                permission_category="ANDROID_DEVICE_READ",
                risk_level="LOW",
                timeout_sec=8.0,
                description="List installed package names",
            )
        )

        # 7. Launch Application
        self.register(
            AndroidOperation(
                operation_id="launch_app",
                command_args=["shell", "monkey", "-p", "{package_name}", "-c", "android.intent.category.LAUNCHER", "1"],
                permission_category="ANDROID_APP_CONTROL",
                risk_level="LOW",
                timeout_sec=10.0,
                validator=lambda p: bool(re.match(r"^[a-zA-Z0-9_\.]+$", str(p.get("package_name", "")))),
                description="Launch an installed application package",
            )
        )

        # 8. Close Application (Force Stop)
        self.register(
            AndroidOperation(
                operation_id="stop_app",
                command_args=["shell", "am", "force-stop", "{package_name}"],
                permission_category="ANDROID_APP_CONTROL",
                risk_level="MEDIUM",
                timeout_sec=5.0,
                validator=lambda p: bool(re.match(r"^[a-zA-Z0-9_\.]+$", str(p.get("package_name", "")))),
                description="Stop application process",
            )
        )

        # 9. Tap / Click
        self.register(
            AndroidOperation(
                operation_id="tap",
                command_args=["shell", "input", "tap", "{x}", "{y}"],
                permission_category="ANDROID_DEVICE_INTERACTION",
                risk_level="LOW",
                timeout_sec=5.0,
                validator=lambda p: int(p.get("x", -1)) >= 0 and int(p.get("y", -1)) >= 0,
                description="Simulate touch tap at screen coordinates",
            )
        )

        # 10. Swipe
        self.register(
            AndroidOperation(
                operation_id="swipe",
                command_args=["shell", "input", "swipe", "{x1}", "{y1}", "{x2}", "{y2}", "{duration}"],
                permission_category="ANDROID_DEVICE_INTERACTION",
                risk_level="LOW",
                timeout_sec=5.0,
                validator=lambda p: all(int(p.get(k, -1)) >= 0 for k in ("x1", "y1", "x2", "y2", "duration")),
                description="Simulate touch swipe gesture",
            )
        )

        # 11. Key Event (Back, Home, Enter, Power, etc.)
        self.register(
            AndroidOperation(
                operation_id="key_event",
                command_args=["shell", "input", "keyevent", "{keycode}"],
                permission_category="ANDROID_DEVICE_INTERACTION",
                risk_level="LOW",
                timeout_sec=5.0,
                validator=lambda p: str(p.get("keycode", "")).isalnum() or str(p.get("keycode", "")).isdigit() or "_" in str(p.get("keycode", "")),
                description="Send Android hardware/virtual keyevent",
            )
        )

        # 12. Text Input
        self.register(
            AndroidOperation(
                operation_id="text_input",
                command_args=["shell", "input", "text", "{text}"],
                permission_category="ANDROID_DEVICE_INTERACTION",
                risk_level="LOW",
                timeout_sec=5.0,
                validator=lambda p: isinstance(p.get("text"), str) and len(p.get("text", "")) <= 500,
                description="Type text into active focused element",
            )
        )

        # 13. Screencap (Screenshot)
        self.register(
            AndroidOperation(
                operation_id="screencap",
                command_args=["shell", "screencap", "-p", "{device_path}"],
                permission_category="ANDROID_DEVICE_READ",
                risk_level="LOW",
                timeout_sec=10.0,
                validator=lambda p: str(p.get("device_path", "")).startswith("/sdcard/") or str(p.get("device_path", "")).startswith("/data/local/tmp/"),
                description="Capture screen image to device storage",
            )
        )

        # 14. File Pull (Phone -> PC)
        self.register(
            AndroidOperation(
                operation_id="pull_file",
                command_args=["pull", "{device_path}", "{pc_path}"],
                permission_category="ANDROID_FILE_READ",
                risk_level="MEDIUM",
                timeout_sec=15.0,
                description="Transfer file from phone to PC sandbox",
            )
        )

        # 15. File Push (PC -> Phone)
        self.register(
            AndroidOperation(
                operation_id="push_file",
                command_args=["push", "{pc_path}", "{device_path}"],
                permission_category="ANDROID_FILE_WRITE",
                risk_level="MEDIUM",
                timeout_sec=15.0,
                description="Transfer file from PC sandbox to phone",
            )
        )

        # 16. Initiate Call Intent
        self.register(
            AndroidOperation(
                operation_id="call_number",
                command_args=["shell", "am", "start", "-a", "android.intent.action.CALL", "-d", "tel:{phone_number}"],
                permission_category="ANDROID_CALL",
                risk_level="HIGH",
                timeout_sec=10.0,
                validator=lambda p: bool(re.match(r"^\+?[0-9]{3,15}$", str(p.get("phone_number", "")))),
                description="Initiate phone call via Android intent",
            )
        )

        # 17. Send SMS Intent
        self.register(
            AndroidOperation(
                operation_id="send_sms",
                command_args=["shell", "service", "call", "isms", "7", "i32", "0", "s16", "com.android.mms", "s16", "{phone_number}", "s16", "null", "s16", "{message}", "s16", "null", "s16", "null"],
                permission_category="ANDROID_MESSAGE",
                risk_level="HIGH",
                timeout_sec=10.0,
                validator=lambda p: bool(re.match(r"^\+?[0-9]{3,15}$", str(p.get("phone_number", "")))) and len(str(p.get("message", ""))) <= 500,
                description="Send SMS message to phone number",
            )
        )

        # 18. Wake Display (Screen on without unlocking)
        self.register(
            AndroidOperation(
                operation_id="wake_display",
                command_args=["shell", "input", "keyevent", "224"],
                permission_category="ANDROID_DEVICE_INTERACTION",
                risk_level="LOW",
                timeout_sec=5.0,
                description="Wake the device display without unlocking",
            )
        )

    def register(self, op: AndroidOperation) -> None:
        self._operations[op.operation_id] = op

    def get_operation(self, operation_id: str) -> AndroidOperation | None:
        return self._operations.get(operation_id)


android_operations = AndroidOperationRegistry()
