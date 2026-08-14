"""
FALSO 4.13 Android Device Manager.

Manages physical ADB connection, device discovery, device-id binding,
pre-execution revalidation, and allowlisted operation dispatch.
"""

from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
import time
from typing import Any

from app.services.automation.android.device_state import (
    AndroidCapabilityState,
    AndroidDeviceState,
    AndroidExecutionState,
    ConnectionState,
)
from app.services.automation.android.operations import android_operations

logger = logging.getLogger(__name__)


class AndroidDeviceManager:
    """Manages ADB interactions and connected Android devices."""

    def __init__(self, adb_path: str = "adb") -> None:
        self.adb_path = adb_path
        self._selected_device_id: str | None = None
        self._cached_devices: dict[str, AndroidDeviceState] = {}
        self.operations = android_operations

    def _resolve_adb_path(self, configured_path: str | None = None) -> str:
        """Resolve the valid ADB binary path from config, env, or known standard paths."""
        candidates: list[str] = []
        if configured_path and configured_path != "adb":
            candidates.append(configured_path)

        env_path = os.environ.get("ANDROID_ADB_PATH")
        if env_path:
            candidates.append(env_path)

        # Standard known Windows platform-tools locations
        candidates.extend([
            r"C:\Users\Admin\Downloads\platform-tools-latest-windows\platform-tools\adb.exe",
            os.path.expanduser(r"~\Downloads\platform-tools-latest-windows\platform-tools\adb.exe"),
            os.path.expandvars(r"%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe"),
            os.path.expandvars(r"%LOCALAPPDATA%\Android\android-sdk\platform-tools\adb.exe"),
            os.path.expandvars(r"%PROGRAMFILES%\Android\platform-tools\adb.exe"),
            os.path.expandvars(r"%PROGRAMFILES(X86)%\Android\platform-tools\adb.exe"),
            "adb.exe",
            "adb",
        ])

        for cand in candidates:
            if os.path.isabs(cand) and os.path.isfile(cand):
                logger.info("[ANDROID][ADB] executable=%s", cand)
                return cand
            w = shutil.which(cand)
            if w:
                logger.info("[ANDROID][ADB] executable=%s", w)
                return w

        return "adb"

    def get_adb_executable(self) -> str:
        return self._resolve_adb_path(self.adb_path)

    def is_adb_available(self) -> bool:
        resolved = self.get_adb_executable()
        if os.path.isabs(resolved) and os.path.isfile(resolved):
            return True
        return shutil.which(resolved) is not None

    def select_device(self, device_id: str) -> bool:
        self._selected_device_id = device_id
        return True

    def get_selected_device_id(self) -> str | None:
        return self._selected_device_id

    # ── Device Discovery ──

    def list_devices(self) -> list[AndroidDeviceState]:
        """Query ADB for connected physical devices."""
        logger.info("[ANDROID][DISCOVERY] Scanning for connected ADB devices.")
        if not self.is_adb_available():
            logger.warning("[ANDROID][DISCOVERY] ADB binary not found.")
            return []

        adb_bin = self.get_adb_executable()
        try:
            res = subprocess.run(
                [adb_bin, "devices", "-l"],
                capture_output=True,
                text=True,
                timeout=5.0,
            )
            if res.returncode != 0:
                logger.error("[ANDROID][ERROR] ADB devices command failed: %s", res.stderr)
                return []

            devices: list[AndroidDeviceState] = []
            lines = res.stdout.strip().splitlines()
            for line in lines[1:]:  # Skip "List of devices attached"
                line = line.strip()
                if not line:
                    continue

                parts = line.split()
                if len(parts) >= 2:
                    dev_id = parts[0]
                    raw_state = parts[1].lower()

                    if raw_state == "device":
                        c_state = ConnectionState.READY
                        is_auth = True
                    elif raw_state == "unauthorized":
                        c_state = ConnectionState.UNAUTHORIZED
                        is_auth = False
                    elif raw_state == "offline":
                        c_state = ConnectionState.OFFLINE
                        is_auth = False
                    else:
                        c_state = ConnectionState.UNKNOWN
                        is_auth = False

                    # Extract model/manufacturer metadata if present
                    model = "Unknown"
                    for p in parts[2:]:
                        if p.startswith("model:"):
                            model = p.split(":", 1)[1]

                    dev_state = AndroidDeviceState(
                        device_id=dev_id,
                        model=model,
                        connection_state=c_state,
                        is_authorized=is_auth,
                    )
                    devices.append(dev_state)
                    self._cached_devices[dev_id] = dev_state

            if len(devices) == 1 and not self._selected_device_id:
                self._selected_device_id = devices[0].device_id

            logger.info("[ANDROID][DISCOVERY] Found %d connected device(s).", len(devices))
            return devices
        except Exception as e:
            logger.error("[ANDROID][ERROR] Failed to discover devices: %s", e)
            return []

    def get_device_info(self, device_id: str | None = None) -> AndroidDeviceState | None:
        """Query detailed properties for a specific device."""
        target_id = device_id or self._selected_device_id
        if not target_id:
            devs = self.list_devices()
            if not devs:
                return None
            target_id = devs[0].device_id

        # Revalidate device presence
        devs = self.list_devices()
        matching = [d for d in devs if d.device_id == target_id]
        if not matching:
            return AndroidDeviceState(device_id=target_id, connection_state=ConnectionState.NOT_CONNECTED)

        dev_state = matching[0]
        if not dev_state.is_authorized:
            return dev_state

        # Query model, manufacturer, and Android release
        mfg = self._run_adb_getprop(target_id, "ro.product.manufacturer")
        model = self._run_adb_getprop(target_id, "ro.product.model")
        version = self._run_adb_getprop(target_id, "ro.build.version.release")
        api = self._run_adb_getprop(target_id, "ro.build.version.sdk")

        dev_state.manufacturer = mfg or dev_state.manufacturer
        dev_state.model = model or dev_state.model
        dev_state.android_version = version or dev_state.android_version
        try:
            dev_state.api_level = int(api) if api else 0
        except ValueError:
            dev_state.api_level = 0

        self._cached_devices[target_id] = dev_state
        return dev_state

    # ── Allowlisted Operation Dispatcher ──

    def execute_operation(
        self,
        operation_id: str,
        params: dict[str, Any] | None = None,
        device_id: str | None = None,
    ) -> dict[str, Any]:
        """Execute a strictly allowlisted Android operation."""
        target_id = device_id or self._selected_device_id
        op_params = params or {}

        # 1. Operation registry check
        op = self.operations.get_operation(operation_id)
        if not op:
            logger.warning("[ANDROID][ERROR] Operation '%s' is not in approved allowlist.", operation_id)
            return {
                "success": False,
                "error": f"Operation '{operation_id}' is UNAVAILABLE or prohibited.",
                "capability_state": AndroidCapabilityState.UNAVAILABLE.value,
                "execution_state": AndroidExecutionState.FAILED.value,
            }

        # 2. Argument validation
        if op.validator and not op.validator(op_params):
            logger.warning("[ANDROID][ERROR] Validation failed for operation '%s' with params %s", operation_id, op_params)
            return {
                "success": False,
                "error": f"Invalid arguments for operation '{operation_id}'.",
                "capability_state": AndroidCapabilityState.DENIED.value,
                "execution_state": AndroidExecutionState.FAILED.value,
            }

        # 3. Real-time Device Revalidation
        if not target_id:
            devs = self.list_devices()
            if not devs:
                return {
                    "success": False,
                    "error": "No Android device connected.",
                    "capability_state": AndroidCapabilityState.UNAVAILABLE.value,
                    "execution_state": AndroidExecutionState.FAILED.value,
                }
            if len(devs) > 1:
                return {
                    "success": False,
                    "error": "Multiple Android devices connected. Please specify which device to use.",
                    "capability_state": AndroidCapabilityState.DENIED.value,
                    "execution_state": AndroidExecutionState.FAILED.value,
                }
            target_id = devs[0].device_id

        # 4. Construct command with device binding (-s <target_id>)
        formatted_args = []
        for arg in op.command_args:
            try:
                formatted_args.append(arg.format(**op_params))
            except KeyError as e:
                return {
                    "success": False,
                    "error": f"Missing required parameter: {e}",
                    "execution_state": AndroidExecutionState.FAILED.value,
                }

        adb_bin = self.get_adb_executable()
        cmd = [adb_bin, "-s", target_id] + formatted_args

        # 5. Execute
        logger.info("[ANDROID][EXECUTE] device=%s operation=%s adb=%s", target_id, operation_id, adb_bin)
        try:
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=op.timeout_sec,
            )
            success = (res.returncode == 0)
            logger.info("[ANDROID][VERIFY] operation=%s returncode=%d", operation_id, res.returncode)
            return {
                "success": success,
                "stdout": res.stdout,
                "stderr": res.stderr,
                "returncode": res.returncode,
                "device_id": target_id,
                "capability_state": AndroidCapabilityState.AVAILABLE.value if success else AndroidCapabilityState.FAILED.value,
                "execution_state": AndroidExecutionState.EXECUTED.value if success else AndroidExecutionState.FAILED.value,
            }
        except subprocess.TimeoutExpired:
            logger.error("[ANDROID][ERROR] Operation '%s' timed out after %fs", operation_id, op.timeout_sec)
            return {
                "success": False,
                "error": f"Operation '{operation_id}' timed out.",
                "capability_state": AndroidCapabilityState.FAILED.value,
                "execution_state": AndroidExecutionState.FAILED.value,
            }
        except Exception as e:
            logger.error("[ANDROID][ERROR] Failed to dispatch operation '%s': %s", operation_id, e)
            return {
                "success": False,
                "error": str(e),
                "capability_state": AndroidCapabilityState.FAILED.value,
                "execution_state": AndroidExecutionState.FAILED.value,
            }

    def _run_adb_getprop(self, device_id: str, prop_name: str) -> str:
        res = self.execute_operation("get_prop", {"prop_name": prop_name}, device_id=device_id)
        return (res.get("stdout") or "").strip()


android_device_manager = AndroidDeviceManager()
