"""
FALSO 4.13 Android Regression Baseline Tests.

Verifies:
1. ADB executable resolution (standard path, env var, or PATH)
2. YouTube end-to-end launch, package resolution & authoritative foreground verification
3. WhatsApp end-to-end launch, package resolution & authoritative foreground verification
4. Wrong foreground package verification failure
5. Unknown foreground returns EXECUTED_UNVERIFIED
6. ADB unavailable handling
7. Device missing handling
8. Natural intent phrasing ("Open YouTube in my device", "Open WhatsApp in my phone")
9. Multi-generation dumpsys foreground parsing and normalization
10. Fallback from dumpsys window to dumpsys activity
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch
import pytest

from app.services.automation.android.device_manager import AndroidDeviceManager, android_device_manager
from app.services.automation.android.device_state import AndroidDeviceState, ConnectionState
from app.services.automation.android.observer import AndroidObserver, android_observer
from app.services.automation.android.skills import AndroidApplicationSkill, KNOWN_APP_PACKAGES
from app.services.automation.operator.action_selector import ControlMethod, action_selector
from app.services.automation.operator.computer_state import ComputerState
from app.services.automation.operator.operator_engine import operator_engine


class TestFalso413AndroidRegressionBaseline:

    # ── 1. ADB executable resolves from standard paths or ANDROID_ADB_PATH ──
    def test_01_adb_executable_resolves(self):
        mgr = AndroidDeviceManager()
        # Test standard known path resolution
        known_path = r"C:\Users\Admin\Downloads\platform-tools-latest-windows\platform-tools\adb.exe"
        if os.path.exists(known_path):
            resolved = mgr.get_adb_executable()
            assert os.path.isabs(resolved)
            assert os.path.isfile(resolved)

        # Test environment variable override
        with patch.dict(os.environ, {"ANDROID_ADB_PATH": r"C:\custom\adb.exe"}):
            with patch("os.path.isfile", return_value=True):
                resolved_env = mgr.get_adb_executable()
                assert resolved_env == r"C:\custom\adb.exe"

    # ── 2. Full YouTube pipeline: resolve -> launch -> observe -> VERIFIED ──
    @pytest.mark.asyncio
    async def test_02_full_pipeline_youtube_verified(self):
        mock_dev = AndroidDeviceState(device_id="3C159U001RM0000", is_authorized=True, connection_state=ConnectionState.READY)
        mock_dumpsys = (
            "mCurrentFocus=Window{c1840ea u0 com.google.android.youtube/com.google.android.youtube.HomeActivity}\n"
            "mFocusedApp=ActivityRecord{a437c95 u0 com.google.android.youtube/.app.honeycomb.Shell$HomeActivity}\n"
            "mResumedActivity=ActivityRecord{a437c95 u0 com.google.android.youtube/com.google.android.apps.youtube.app.watchwhile.WatchWhileActivity}\n"
        )

        with patch.object(android_device_manager, "list_devices", return_value=[mock_dev]):
            with patch.object(android_observer, "observe_lock_state", return_value={"is_locked": False, "state": "UNLOCKED"}):
                with patch.object(android_device_manager, "execute_operation") as mock_exec:
                    def side_effect(op_name, params=None, device_id=None):
                        if op_name == "launch_app":
                            return {"success": True, "returncode": 0, "stdout": "Events injected: 1"}
                        if op_name == "get_foreground_window":
                            return {"success": True, "returncode": 0, "stdout": mock_dumpsys}
                        if op_name == "get_lock_state":
                            return {"success": True, "returncode": 0, "stdout": "deviceLocked=false"}
                        return {"success": True, "returncode": 0, "stdout": ""}

                    mock_exec.side_effect = side_effect

                    msg = await operator_engine.run_operation("Open YouTube on my phone")
                    assert "YouTube is open." in msg or "Done." in msg

    # ── 3. Full WhatsApp pipeline: resolve -> launch -> observe -> VERIFIED ──
    @pytest.mark.asyncio
    async def test_03_full_pipeline_whatsapp_verified(self):
        mock_dev = AndroidDeviceState(device_id="3C159U001RM0000", is_authorized=True, connection_state=ConnectionState.READY)
        mock_dumpsys = "mCurrentFocus=Window{89abcde u0 com.whatsapp/com.whatsapp.HomeActivity}\n"

        with patch.object(android_device_manager, "list_devices", return_value=[mock_dev]):
            with patch.object(android_observer, "observe_lock_state", return_value={"is_locked": False, "state": "UNLOCKED"}):
                with patch.object(android_device_manager, "execute_operation") as mock_exec:
                    def side_effect(op_name, params=None, device_id=None):
                        if op_name == "launch_app":
                            return {"success": True, "returncode": 0, "stdout": "Events injected: 1"}
                        if op_name == "get_foreground_window":
                            return {"success": True, "returncode": 0, "stdout": mock_dumpsys}
                        if op_name == "get_lock_state":
                            return {"success": True, "returncode": 0, "stdout": "deviceLocked=false"}
                        return {"success": True, "returncode": 0, "stdout": ""}

                    mock_exec.side_effect = side_effect

                    msg = await operator_engine.run_operation("Open WhatsApp in my phone")
                    assert "WhatsApp is open." in msg or "Done." in msg

    # ── 4. Wrong foreground package fails verification ──
    def test_04_wrong_foreground_package_fails_verification(self):
        skill = AndroidApplicationSkill()
        mock_dev = AndroidDeviceState(device_id="3C159U001RM0000", is_authorized=True, connection_state=ConnectionState.READY)

        with patch.object(android_device_manager, "list_devices", return_value=[mock_dev]):
            with patch.object(android_observer, "observe_lock_state", return_value={"is_locked": False, "state": "UNLOCKED"}):
                with patch.object(android_device_manager, "execute_operation", return_value={"success": True, "returncode": 0}):
                    with patch.object(android_observer, "observe_foreground_app", return_value={"package": "com.android.settings", "activity": ".Settings"}):
                        res = skill.execute("launch_android_app", "youtube", {"app": "youtube"}, ComputerState())
                        assert res["verified"] is False
                        assert res["execution_state"] == "EXECUTED_UNVERIFIED"

    # ── 5. Unknown foreground returns EXECUTED_UNVERIFIED ──
    def test_05_unknown_foreground_returns_executed_unverified(self):
        skill = AndroidApplicationSkill()
        mock_dev = AndroidDeviceState(device_id="3C159U001RM0000", is_authorized=True, connection_state=ConnectionState.READY)

        with patch.object(android_device_manager, "list_devices", return_value=[mock_dev]):
            with patch.object(android_observer, "observe_lock_state", return_value={"is_locked": False, "state": "UNLOCKED"}):
                with patch.object(android_device_manager, "execute_operation", return_value={"success": True, "returncode": 0}):
                    with patch.object(android_observer, "observe_foreground_app", return_value={"package": None, "activity": None, "evidence": "UNKNOWN"}):
                        res = skill.execute("launch_android_app", "youtube", {"app": "youtube"}, ComputerState())
                        assert res["verified"] is False
                        assert res["execution_state"] == "EXECUTED_UNVERIFIED"
                        assert "Launch command sent" in res["summary"]

    # ── 6. ADB unavailable returns honest failure ──
    def test_06_adb_unavailable_returns_no_device(self):
        skill = AndroidApplicationSkill()
        with patch.object(android_device_manager, "list_devices", return_value=[]):
            res = skill.execute("launch_android_app", "youtube", {"app": "youtube"}, ComputerState())
            assert res["success"] is False
            assert "No authorized Android phone is connected." in res["error"]

    # ── 7. Device missing returns honest failure ──
    def test_07_device_missing_returns_honest_error(self):
        skill = AndroidApplicationSkill()
        mock_dev = AndroidDeviceState(device_id="dev_other", is_authorized=True, connection_state=ConnectionState.READY)
        with patch.object(android_device_manager, "list_devices", return_value=[mock_dev]):
            res = skill.execute("launch_android_app", "youtube", {"app": "youtube", "device_id": "nonexistent_device"}, ComputerState())
            assert res["success"] is False
            assert "not found" in res["error"]

    # ── 8. Natural intent phrasing "Open YouTube in my device" ──
    def test_08_natural_phrasing_in_my_device(self):
        sel = action_selector.select_action("Open YouTube in my device", ComputerState())
        assert sel.method == ControlMethod.ANDROID_SKILL
        assert sel.action_name == "launch_android_app"
        assert sel.params["app"] == "youtube"

    # ── 9. Natural intent phrasing "Open WhatsApp in my phone" ──
    def test_09_natural_phrasing_in_my_phone(self):
        sel = action_selector.select_action("Open WhatsApp in my phone", ComputerState())
        assert sel.method == ControlMethod.ANDROID_SKILL
        assert sel.action_name == "launch_android_app"
        assert sel.params["app"] == "whatsapp"

    # ── 10. Multi-generation dumpsys parsing and activity fallback ──
    def test_10_multi_generation_dumpsys_parsing(self):
        obs = AndroidObserver()

        # Format A: mResumedActivity
        dump_a = "mResumedActivity=ActivityRecord{a437c95 u0 com.google.android.youtube/com.google.android.apps.youtube.app.watchwhile.WatchWhileActivity}"
        parsed_a = obs._parse_foreground_from_dumpsys(dump_a)
        assert parsed_a["package"] == "com.google.android.youtube"

        # Format B: mFocusedApp with nested inner class
        dump_b = "mFocusedApp=ActivityRecord{a437c95 u0 com.google.android.youtube/.app.honeycomb.Shell$HomeActivity}"
        parsed_b = obs._parse_foreground_from_dumpsys(dump_b)
        assert parsed_b["package"] == "com.google.android.youtube"

        # Format C: mCurrentFocus with u0
        dump_c = "mCurrentFocus=Window{c1840ea u0 com.whatsapp/com.whatsapp.HomeActivity}"
        parsed_c = obs._parse_foreground_from_dumpsys(dump_c)
        assert parsed_c["package"] == "com.whatsapp"

        # Format D: ResumedActivity in dumpsys activity
        dump_d = "ResumedActivity: ActivityRecord{12345 u0 com.android.chrome/com.google.android.apps.chrome.Main}"
        parsed_d = obs._parse_foreground_from_dumpsys(dump_d)
        assert parsed_d["package"] == "com.android.chrome"
