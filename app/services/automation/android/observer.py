"""
FALSO 4.13 Android Device Observer.

Provides authoritative state observation for connected Android devices with strict evidence classification:
- OBSERVED (directly parsed from dumpsys/adb output)
- INFERRED
- UNKNOWN
"""

from __future__ import annotations

import logging
import re
from typing import Any

from app.services.automation.android.device_manager import android_device_manager
from app.services.automation.android.device_state import AndroidDeviceState

logger = logging.getLogger(__name__)


class AndroidObserver:
    """Collects authoritative state from connected Android device."""

    def __init__(self, device_manager=None) -> None:
        self.device_manager = device_manager or android_device_manager

    def observe_battery(self, device_id: str | None = None) -> dict[str, Any]:
        """Observe battery level and charging state."""
        res = self.device_manager.execute_operation("get_battery", device_id=device_id)
        if not res.get("success"):
            return {"level": None, "is_charging": None, "evidence": "UNKNOWN"}

        stdout = res.get("stdout", "")
        level_m = re.search(r"level:\s*(\d+)", stdout)
        status_m = re.search(r"status:\s*(\d+)", stdout)
        usb_m = re.search(r"USB powered:\s*(true|false)", stdout, re.IGNORECASE)

        level = int(level_m.group(1)) if level_m else None
        is_charging = (status_m and status_m.group(1) == "2") or (usb_m and usb_m.group(1).lower() == "true")

        return {
            "level": level,
            "is_charging": bool(is_charging),
            "evidence": "OBSERVED",
        }

    def observe_storage(self, device_id: str | None = None) -> dict[str, Any]:
        """Observe /data partition free space in GB."""
        res = self.device_manager.execute_operation("get_storage", device_id=device_id)
        if not res.get("success"):
            return {"free_gb": None, "evidence": "UNKNOWN"}

        stdout = res.get("stdout", "")
        # Parse df output
        lines = stdout.strip().splitlines()
        free_gb = None
        for line in lines[1:]:
            parts = line.split()
            if len(parts) >= 4:
                try:
                    # In 1K blocks
                    free_blocks = float(parts[3])
                    free_gb = round(free_blocks / (1024 * 1024), 2)
                    break
                except ValueError:
                    continue

        return {
            "free_gb": free_gb,
            "evidence": "OBSERVED" if free_gb is not None else "UNKNOWN",
        }

    def observe_foreground_app(self, device_id: str | None = None) -> dict[str, Any]:
        """
        Authoritatively identify current focused package and activity using Android-specific state.
        Supports multi-generation Android output formats (ActivityRecord, AppWindowToken, Window, topResumedActivity).
        """
        # Primary: dumpsys window windows
        res = self.device_manager.execute_operation("get_foreground_window", device_id=device_id)
        stdout = res.get("stdout", "") if res.get("success") else ""

        parsed = self._parse_foreground_from_dumpsys(stdout)
        if parsed.get("package"):
            logger.info("[ANDROID][OBSERVE] Found foreground package=%s activity=%s from window dump", parsed["package"], parsed["activity"])
            return parsed

        # Secondary Fallback: dumpsys activity activities
        res_act = self.device_manager.execute_operation("get_foreground_activity", device_id=device_id)
        stdout_act = res_act.get("stdout", "") if res_act.get("success") else ""
        parsed_act = self._parse_foreground_from_dumpsys(stdout_act)
        if parsed_act.get("package"):
            logger.info("[ANDROID][OBSERVE] Found foreground package=%s activity=%s from activity dump", parsed_act["package"], parsed_act["activity"])
            return parsed_act

        logger.warning("[ANDROID][OBSERVE] Unable to authoritatively determine Android foreground package.")
        return {"package": None, "activity": None, "evidence": "UNKNOWN"}

    def _parse_foreground_from_dumpsys(self, stdout: str) -> dict[str, Any]:
        """Extract and normalize package and activity from Android dumpsys text."""
        if not stdout:
            return {"package": None, "activity": None, "evidence": "UNKNOWN"}

        patterns = [
            # mResumedActivity=ActivityRecord{... com.package/com.package.Activity}
            r"mResumedActivity=(?:ActivityRecord|AppWindowToken)\{[^\}]*\s+(?:u\d+\s+)?([a-zA-Z0-9_\.]+)/([a-zA-Z0-9_\.\$]+)",
            # mFocusedApp=ActivityRecord{... com.package/...}
            r"mFocusedApp=(?:ActivityRecord|AppWindowToken)\{[^\}]*\s+(?:u\d+\s+)?([a-zA-Z0-9_\.]+)/([a-zA-Z0-9_\.\$]+)",
            # topResumedActivity=ActivityRecord{... com.package/...}
            r"topResumedActivity=(?:ActivityRecord|AppWindowToken)\{[^\}]*\s+(?:u\d+\s+)?([a-zA-Z0-9_\.]+)/([a-zA-Z0-9_\.\$]+)",
            # mCurrentFocus=Window{... com.package/...}
            r"mCurrentFocus=Window\{[^\}]*\s+(?:u\d+\s+)?([a-zA-Z0-9_\.]+)/([a-zA-Z0-9_\.\$]+)",
            # mFocusedWindow=Window{... com.package/...}
            r"mFocusedWindow=Window\{[^\}]*\s+(?:u\d+\s+)?([a-zA-Z0-9_\.]+)/([a-zA-Z0-9_\.\$]+)",
            # ResumedActivity: ActivityRecord{... com.package/...}
            r"ResumedActivity:\s+(?:ActivityRecord|AppWindowToken)\{[^\}]*\s+(?:u\d+\s+)?([a-zA-Z0-9_\.]+)/([a-zA-Z0-9_\.\$]+)",
            # generic ComponentInfo{com.package/com.package.Activity}
            r"ComponentInfo\{([a-zA-Z0-9_\.]+)/([a-zA-Z0-9_\.\$]+)\}",
        ]

        for pat in patterns:
            m = re.search(pat, stdout)
            if m:
                pkg = m.group(1).strip()
                act = m.group(2).strip()
                return {
                    "package": pkg,
                    "activity": act,
                    "evidence": "OBSERVED",
                }

        return {"package": None, "activity": None, "evidence": "UNKNOWN"}

    def observe_lock_state(self, device_id: str | None = None) -> dict[str, Any]:
        """Determine if device display is locked or unlocked."""
        res = self.device_manager.execute_operation("get_lock_state", device_id=device_id)
        if not res.get("success"):
            return {"is_locked": None, "state": "UNKNOWN", "evidence": "UNKNOWN"}

        stdout = res.get("stdout", "")
        # Search for mCurrentUserIsTrustmanaged=... mTrustIsManaged=... or mUserIsUnlocked=...
        if "deviceLocked=true" in stdout or "mDeviceLocked=true" in stdout:
            return {"is_locked": True, "state": "LOCKED", "evidence": "OBSERVED"}
        if "deviceLocked=false" in stdout or "mDeviceLocked=false" in stdout:
            return {"is_locked": False, "state": "UNLOCKED", "evidence": "OBSERVED"}

        return {"is_locked": False, "state": "UNLOCKED", "evidence": "INFERRED"}

    def observe_installed_packages(self, device_id: str | None = None) -> list[str]:
        """List all installed package names."""
        res = self.device_manager.execute_operation("list_packages", device_id=device_id)
        if not res.get("success"):
            return []

        stdout = res.get("stdout", "")
        packages = []
        for line in stdout.splitlines():
            line = line.strip()
            if line.startswith("package:"):
                packages.append(line.replace("package:", "").strip())
        return packages


android_observer = AndroidObserver()
