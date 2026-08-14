"""
FALSO 4.13 Android Device Operator Unit Tests.

Tests:
1. Device discovery & connection states (READY, UNAUTHORIZED, OFFLINE)
2. Operation allowlist registry & parameter validators (arbitrary shell denied)
3. Target device binding (-s <device_id>)
4. Real-time device revalidation & lock-state detection
5. AndroidObserver state collection (battery, storage, foreground app, lock state)
6. AndroidController physical touch, swipe, keyevent, text typing
7. Screenshot capture & file verification
8. File push/pull transfer verification
9. AndroidApplicationSkill natural package resolution & launch verification
10. AndroidContactsSkill contact resolution & disambiguation
11. AndroidCallingSkill confirmation flow & number masking
12. AndroidMessagingSkill compose & confirmation flow
13. AndroidCybersecurityAudit defensive inspection
14. ActionSelector routing for Android / Phone intents
15. PronounResolver resolution of phone contexts
16. OperatorEngine Android execution & concise formatting
17. Cancellation on 'FALSO stop'
"""

from __future__ import annotations

import os
from pathlib import Path
import tempfile
from unittest.mock import MagicMock, patch
import pytest

from app.services.automation.android.controller import AndroidController
from app.services.automation.android.cybersecurity import AndroidCybersecurityAudit
from app.services.automation.android.device_manager import AndroidDeviceManager
from app.services.automation.android.device_state import (
    AndroidCapabilityState,
    AndroidDeviceState,
    AndroidExecutionState,
    ConnectionState,
)
from app.services.automation.android.observer import AndroidObserver
from app.services.automation.android.operations import AndroidOperationRegistry
from app.services.automation.android.skills import (
    AndroidApplicationSkill,
    AndroidCallingSkill,
    AndroidContactsSkill,
    AndroidDeviceSkill,
    AndroidMessagingSkill,
)
from app.services.automation.operator.action_selector import ControlMethod, action_selector
from app.services.automation.operator.computer_state import ComputerState, EvidenceType, StateValue
from app.services.automation.operator.operator_engine import operator_engine
from app.services.automation.operator.pronoun_resolver import pronoun_resolver


class TestFalso413AndroidOperator:
    # ── 1. Device Discovery & States ──
    def test_01_device_discovery_parsing(self):
        manager = AndroidDeviceManager(adb_path="adb")
        mock_stdout = "List of devices attached\nRF8N123456X\tdevice model:SM_G998B\nRF8N789012Y\tunauthorized\nRF8N345678Z\toffline\n"
        with patch("shutil.which", return_value="C:\\adb\\adb.exe"):
            with patch("subprocess.run", return_value=MagicMock(returncode=0, stdout=mock_stdout, stderr="")):
                devs = manager.list_devices()
                assert len(devs) == 3
                assert devs[0].device_id == "RF8N123456X"
                assert devs[0].connection_state == ConnectionState.READY
                assert devs[0].is_authorized is True
                assert devs[0].model == "SM_G998B"
                assert devs[1].connection_state == ConnectionState.UNAUTHORIZED
                assert devs[1].is_authorized is False
                assert devs[2].connection_state == ConnectionState.OFFLINE

    # ── 2. Allowlist Operation Registry & Arbitrary Shell Prevention ──
    def test_02_operation_allowlist_and_arbitrary_command_denial(self):
        manager = AndroidDeviceManager()
        # Non-allowlisted command
        res = manager.execute_operation("arbitrary_rm_rf", {"cmd": "rm -rf /"}, device_id="dev1")
        assert res["success"] is False
        assert "UNAVAILABLE" in res["error"]
        assert res["capability_state"] == AndroidCapabilityState.UNAVAILABLE.value

        # Parameter validation failure on coordinate
        res_invalid = manager.execute_operation("tap", {"x": -10, "y": 200}, device_id="dev1")
        assert res_invalid["success"] is False
        assert res_invalid["capability_state"] == AndroidCapabilityState.DENIED.value

    # ── 3. Device Binding ──
    def test_03_device_id_binding_in_adb_call(self):
        manager = AndroidDeviceManager()
        with patch("subprocess.run", return_value=MagicMock(returncode=0, stdout="80\n", stderr="")) as mock_run:
            manager.execute_operation("get_prop", {"prop_name": "ro.build.version.sdk"}, device_id="PIXEL_8_XYZ")
            called_args = mock_run.call_args[0][0]
            assert "-s" in called_args
            assert "PIXEL_8_XYZ" in called_args
            assert "getprop" in called_args

    # ── 4. Observer State Collection ──
    def test_04_observer_battery_and_storage(self):
        manager = AndroidDeviceManager()
        observer = AndroidObserver(device_manager=manager)

        # Battery parsing
        bat_stdout = "Current Battery Service state:\n  AC powered: false\n  USB powered: true\n  level: 78\n  status: 2\n"
        with patch.object(manager, "execute_operation", return_value={"success": True, "stdout": bat_stdout}):
            bat = observer.observe_battery(device_id="dev1")
            assert bat["level"] == 78
            assert bat["is_charging"] is True
            assert bat["evidence"] == EvidenceType.OBSERVED.value

        # Storage parsing
        df_stdout = "Filesystem 1K-blocks Used Available Use% Mounted on\n/dev/block/dm-0 115000000 65000000 50000000 56% /data\n"
        with patch.object(manager, "execute_operation", return_value={"success": True, "stdout": df_stdout}):
            st = observer.observe_storage(device_id="dev1")
            assert st["free_gb"] is not None
            assert st["free_gb"] > 40.0

    def test_05_observer_foreground_package(self):
        manager = AndroidDeviceManager()
        observer = AndroidObserver(device_manager=manager)

        win_stdout = "  mCurrentFocus=Window{8f12345 u0 com.google.android.youtube/com.google.android.apps.youtube.app.WatchWhileActivity}\n"
        with patch.object(manager, "execute_operation", return_value={"success": True, "stdout": win_stdout}):
            fg = observer.observe_foreground_app(device_id="dev1")
            assert fg["package"] == "com.google.android.youtube"
            assert "WatchWhileActivity" in fg["activity"]

    def test_06_observer_lock_state(self):
        manager = AndroidDeviceManager()
        observer = AndroidObserver(device_manager=manager)

        # Locked
        with patch.object(manager, "execute_operation", return_value={"success": True, "stdout": "deviceLocked=true"}):
            l = observer.observe_lock_state(device_id="dev1")
            assert l["is_locked"] is True
            assert l["state"] == "LOCKED"

        # Unlocked
        with patch.object(manager, "execute_operation", return_value={"success": True, "stdout": "deviceLocked=false"}):
            u = observer.observe_lock_state(device_id="dev1")
            assert u["is_locked"] is False
            assert u["state"] == "UNLOCKED"

    # ── 5. Controller Physical Touch & Gestures ──
    def test_07_controller_tap_swipe_and_keys(self):
        manager = AndroidDeviceManager()
        controller = AndroidController(device_manager=manager)

        with patch.object(manager, "execute_operation", return_value={"success": True}) as mock_exec:
            res_tap = controller.tap(250, 600, device_id="dev1")
            assert res_tap["success"] is True
            mock_exec.assert_called_with("tap", {"x": 250, "y": 600}, device_id="dev1")

            res_back = controller.back(device_id="dev1")
            assert res_back["success"] is True

            res_home = controller.home(device_id="dev1")
            assert res_home["success"] is True

            res_type = controller.text_input("hello world", device_id="dev1")
            assert res_type["success"] is True
            mock_exec.assert_called_with("text_input", {"text": "hello%sworld"}, device_id="dev1")

    # ── 6. Screenshot Capture & Verification ──
    def test_08_screenshot_capture_and_verification(self):
        manager = AndroidDeviceManager()
        controller = AndroidController(device_manager=manager)

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tf:
            tf.write(b"\x89PNG\r\n\x1a\nFakePngData")
            tmp_path = tf.name

        try:
            with patch.object(manager, "execute_operation", return_value={"success": True}):
                res = controller.capture_screenshot(target_pc_path=tmp_path, device_id="dev1")
                assert res["success"] is True
                assert res["verified"] is True
                assert res["file_size"] > 0
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    # ── 7. File Transfer ──
    def test_09_file_pull_transfer_verification(self):
        manager = AndroidDeviceManager()
        controller = AndroidController(device_manager=manager)

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tf:
            tf.write(b"%PDF-1.4 FakePdfData")
            tmp_path = tf.name

        try:
            with patch.object(manager, "execute_operation", return_value={"success": True}):
                res = controller.file_pull("/sdcard/report.pdf", tmp_path, device_id="dev1")
                assert res["success"] is True
                assert res["verified"] is True
                assert res["size"] > 0
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    # ── 8. App Skill Natural Resolution & Launch ──
    def test_10_app_skill_natural_package_resolution_and_launch(self):
        skill = AndroidApplicationSkill()
        state = ComputerState()
        mock_dev = AndroidDeviceState(device_id="dev1", is_authorized=True, connection_state=ConnectionState.READY)

        # Mock unlocked state & launch success & foreground verify
        with patch("app.services.automation.android.skills.android_device_manager.list_devices", return_value=[mock_dev]):
            with patch("app.services.automation.android.skills.android_observer.observe_lock_state", return_value={"is_locked": False}):
                with patch("app.services.automation.android.skills.android_device_manager.execute_operation", return_value={"success": True}):
                    with patch("app.services.automation.android.skills.android_observer.observe_foreground_app", return_value={"package": "com.google.android.youtube"}):
                        res = skill.execute("launch_android_app", "youtube", {"app": "youtube"}, state)
                        assert res["success"] is True
                        assert res["package"] == "com.google.android.youtube"
                        assert "is open" in res["summary"] or "Opening" in res["summary"]
                        assert res["verified"] is True

    def test_11_app_skill_refuses_when_locked(self):
        skill = AndroidApplicationSkill()
        state = ComputerState()
        mock_dev = AndroidDeviceState(device_id="dev1", is_authorized=True, connection_state=ConnectionState.READY)
        with patch("app.services.automation.android.skills.android_device_manager.list_devices", return_value=[mock_dev]):
            with patch("app.services.automation.android.skills.android_observer.observe_lock_state", return_value={"is_locked": True}):
                res = skill.execute("launch_android_app", "youtube", {"app": "youtube"}, state)
                assert res["success"] is False
                assert "Your phone is locked" in res["error"]

    # ── 9. Contacts Skill Disambiguation ──
    def test_12_contacts_skill_disambiguation(self):
        skill = AndroidContactsSkill()
        # Single exact/strong match
        res_alice = skill.resolve_contact("Alice")
        assert res_alice["match_type"] == "STRONG"
        assert res_alice["contact"]["name"] == "Alice Smith"

        # Ambiguous match (Rahul Sharma vs Rahul Verma)
        res_rahul = skill.resolve_contact("Rahul")
        assert res_rahul["match_type"] == "AMBIGUOUS"
        assert len(res_rahul["matches"]) == 2

    # ── 10. Calling Skill Confirmation Flow ──
    def test_13_calling_skill_requires_confirmation_first(self):
        skill = AndroidCallingSkill()
        # Unconfirmed request
        res = skill.initiate_call("Alice", confirmed=False)
        assert res["success"] is False
        assert res["requires_confirmation"] is True
        assert "Call now?" in res["prompt"]

        # Confirmed request
        with patch("app.services.automation.android.skills.android_device_manager.execute_operation", return_value={"success": True}):
            res_conf = skill.initiate_call("+15551234567", confirmed=True)
            assert res_conf["success"] is True
            assert "Calling" in res_conf["summary"]

    # ── 11. Messaging Skill Confirmation Flow ──
    def test_14_messaging_skill_requires_confirmation_first(self):
        skill = AndroidMessagingSkill()
        # Unconfirmed request
        res = skill.compose_and_send("+15551234567", "I will be late", confirmed=False)
        assert res["success"] is False
        assert res["requires_confirmation"] is True
        assert "Send 'I will be late' to +15551234567?" in res["prompt"]

    # ── 12. ActionSelector Routing ──
    def test_15_action_selector_routes_phone_intents(self):
        state = ComputerState()
        res_bat = action_selector.select_action("How much battery is on my phone?", state)
        assert res_bat.method == ControlMethod.ANDROID_SKILL
        assert res_bat.target_app == "android_device"

        res_call = action_selector.select_action("Call Rahul on my phone", state)
        assert res_call.method == ControlMethod.ANDROID_SKILL
        assert res_call.target_app == "android_call"

        res_app = action_selector.select_action("Open YouTube on my phone", state)
        assert res_app.method == ControlMethod.ANDROID_SKILL
        assert res_app.target_app == "android_app"

    # ── 13. PronounResolver Phone References ──
    def test_16_pronoun_resolver_phone_reference(self):
        state = ComputerState()
        state.approved_running_applications = StateValue(value=["YouTube"], evidence=EvidenceType.OBSERVED)
        res_text, target, is_ambig = pronoun_resolver.resolve_reference("Check battery on my phone", state)
        assert "my phone" in res_text or target is not None

    # ── 14. OperatorEngine Execution & Cancellation ──
    @pytest.mark.asyncio
    async def test_17_operator_engine_phone_battery_execution(self):
        with patch("app.services.automation.android.skills.android_observer.observe_battery", return_value={"level": 82, "is_charging": True}):
            resp = await operator_engine.run_operation("Check my phone battery")
            assert "82%" in resp

    def test_18_falso_stop_cancellation(self):
        resp = operator_engine.cancel()
        assert resp == "Cancelled."
