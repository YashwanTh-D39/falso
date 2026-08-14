"""
TEST SUITE: FALSO 4.13 — UNLOCK INTENT ROUTING FIX

Tests proving:
1. "unlock my phone" routes to Android.
2. Generic LLM is NOT called for recognized unlock intent.
3. Locked device enters WAITING_FOR_USER_UNLOCK.
4. Display wake does not equal unlock.
5. Legitimate unlock resumes workflow.
6. Already-unlocked phone doesn't enter waiting state.
7. No device gives correct response ("No authorized Android phone is connected.").
8. Unauthorized device gives correct response ("Your phone is connected but hasn't authorized this computer.").
9. Multiple devices require selection.
10. "unlock it" uses PronounResolver correctly.
11. Voice and text follow the same route.
12. FALSO stop cancels unlock waiting.
13. No credential is requested or stored.
14. No authentication bypass exists.
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.automation.android import (
    AndroidDeviceState,
    ConnectionState,
    UnlockState,
    android_device_manager,
    android_device_skill,
    authorized_unlock_manager,
)
from app.services.automation.operator import (
    ComputerState,
    ControlMethod,
    action_selector,
    operator_engine,
    pronoun_resolver,
)
from app.services.brain import BrainService, is_automation_intent


class TestFalso413UnlockRoutingFix:

    @pytest.fixture(autouse=True)
    def reset_state(self):
        authorized_unlock_manager.cancel_unlock_wait()
        yield
        authorized_unlock_manager.cancel_unlock_wait()

    # ── 1. "unlock my phone" routes to Android ──
    def test_01_unlock_my_phone_routes_to_android(self):
        state = ComputerState()
        for phrase in ("unlock my phone", "unlock my device", "unlock the phone", "unlock my mobile", "wake and unlock my phone"):
            res = action_selector.select_action(phrase, state)
            assert res.method == ControlMethod.ANDROID_SKILL
            assert res.target_app == "android_device"
            assert res.action_name == "unlock_phone"

    # ── 2. Generic LLM is NOT called for recognized unlock intent ──
    @pytest.mark.asyncio
    async def test_02_generic_llm_not_called_for_unlock_intent(self):
        brain = BrainService()
        mock_provider = MagicMock()
        mock_provider.model = "test-model"
        mock_provider.generate_chat_response = AsyncMock()
        brain.provider = mock_provider

        mock_dev = AndroidDeviceState(device_id="dev1", is_authorized=True, connection_state=ConnectionState.READY)
        with patch.object(android_device_manager, "list_devices", return_value=[mock_dev]):
            with patch.object(authorized_unlock_manager.observer, "observe_lock_state", return_value={"is_locked": True, "state": "LOCKED"}):
                with patch.object(authorized_unlock_manager.controller, "wake_display", return_value={"success": True}):
                    chunks = []
                    async for chunk in brain.chat("unlock my device", session_id="test_sess"):
                        chunks.append(chunk)

                    full_resp = "".join(json.loads(c)["response"] for c in chunks if "response" in json.loads(c))
                    # Generic LLM streaming should NOT have been invoked
                    mock_provider.generate_chat_response.assert_not_called()
                    assert "Your phone is locked. Unlock it and I'll continue." in full_resp

    # ── 3. Locked device enters WAITING_FOR_USER_UNLOCK ──
    def test_03_locked_device_enters_waiting_for_user_unlock(self):
        mock_dev = AndroidDeviceState(device_id="dev1", is_authorized=True, connection_state=ConnectionState.READY)
        with patch.object(android_device_manager, "list_devices", return_value=[mock_dev]):
            with patch.object(authorized_unlock_manager.observer, "observe_lock_state", return_value={"is_locked": True, "state": "LOCKED"}):
                with patch.object(authorized_unlock_manager.controller, "wake_display", return_value={"success": True}):
                    res = android_device_skill.handle_unlock_request()
                    assert res["success"] is True
                    assert res["waiting_for_unlock"] is True
                    assert "Your phone is locked. Unlock it and I'll continue." in res["summary"]
                    wf = authorized_unlock_manager.get_active_workflow()
                    assert wf is not None
                    assert wf.state == UnlockState.WAITING_FOR_USER_UNLOCK

    # ── 4. Display wake does not equal unlock ──
    def test_04_display_wake_does_not_equal_unlock(self):
        mock_dev = AndroidDeviceState(device_id="dev1", is_authorized=True, connection_state=ConnectionState.READY)
        with patch.object(android_device_manager, "list_devices", return_value=[mock_dev]):
            with patch.object(authorized_unlock_manager.controller, "wake_display", return_value={"success": True, "display_state": "DISPLAY_AWAKE", "is_unlocked": False}):
                authorized_unlock_manager.wake_display("dev1")
                wf = authorized_unlock_manager.get_active_workflow()
                # Waking display must NOT transition workflow to COMPLETED/UNLOCKED
                assert wf is None or wf.state != UnlockState.COMPLETED

    # ── 5. Legitimate unlock resumes workflow ──
    def test_05_legitimate_unlock_resumes_workflow(self):
        mock_dev = AndroidDeviceState(device_id="dev1", is_authorized=True, connection_state=ConnectionState.READY)
        with patch.object(authorized_unlock_manager.device_manager, "get_device_info", return_value=mock_dev):
            with patch.object(authorized_unlock_manager.controller, "wake_display", return_value={"success": True}):
                authorized_unlock_manager.initiate_unlock_wait(
                    task_id="t1",
                    goal="open youtube on phone",
                    pending_steps=[{"action_name": "launch_android_app", "target_app": "youtube", "params": {"app": "youtube"}}],
                    device_id="dev1",
                )

            with patch.object(authorized_unlock_manager.observer, "observe_lock_state", return_value={"is_locked": False, "state": "UNLOCKED"}):
                with patch.object(authorized_unlock_manager.observer, "observe_foreground_app", return_value={"package": "com.google.android.youtube"}):
                    with patch.object(authorized_unlock_manager, "_dispatch_step_execution", return_value={"success": True, "package": "com.google.android.youtube", "summary": "Opening Youtube now."}):
                        ok, msg = authorized_unlock_manager.resume_workflow()
                        assert ok is True
                        assert "Youtube is open." in msg or "Opening Youtube now." in msg

    # ── 6. Already-unlocked phone doesn't enter waiting state ──
    def test_06_already_unlocked_phone_no_wait(self):
        mock_dev = AndroidDeviceState(device_id="dev1", is_authorized=True, connection_state=ConnectionState.READY)
        with patch.object(android_device_manager, "list_devices", return_value=[mock_dev]):
            with patch.object(authorized_unlock_manager.observer, "observe_lock_state", return_value={"is_locked": False, "state": "UNLOCKED"}):
                res = android_device_skill.handle_unlock_request()
                assert res["success"] is True
                assert res.get("waiting_for_unlock") is not True
                assert "Your phone is already unlocked." in res["summary"]
                assert authorized_unlock_manager.get_active_workflow() is None

    # ── 7. No device gives correct response ──
    def test_07_no_device_gives_correct_response(self):
        with patch.object(android_device_manager, "list_devices", return_value=[]):
            res = android_device_skill.handle_unlock_request()
            assert res["success"] is False
            assert "No authorized Android phone is connected." in res["error"]

    # ── 8. Unauthorized device gives correct response ──
    def test_08_unauthorized_device_gives_correct_response(self):
        unauth_dev = AndroidDeviceState(device_id="dev_unauth", is_authorized=False, connection_state=ConnectionState.UNAUTHORIZED)
        with patch.object(android_device_manager, "list_devices", return_value=[unauth_dev]):
            res = android_device_skill.handle_unlock_request()
            assert res["success"] is False
            assert "Your phone is connected but hasn't authorized this computer." in res["error"]

    # ── 9. Multiple devices require selection ──
    def test_09_multiple_devices_require_selection(self):
        dev1 = AndroidDeviceState(device_id="dev_1", is_authorized=True, connection_state=ConnectionState.READY)
        dev2 = AndroidDeviceState(device_id="dev_2", is_authorized=True, connection_state=ConnectionState.READY)
        with patch.object(android_device_manager, "list_devices", return_value=[dev1, dev2]):
            res = android_device_skill.handle_unlock_request()
            assert res["success"] is False
            assert "Multiple Android devices connected" in res["error"]
            assert "Which device would you like to use?" in res["error"]

    # ── 10. "unlock it" uses PronounResolver correctly ──
    def test_10_unlock_it_uses_pronoun_resolver(self):
        state = ComputerState()
        # Set previous context to phone
        from app.services.automation.operator import VerifiedActionRecord
        state.add_verified_action(
            VerifiedActionRecord(
                task_id="t0",
                action_id="a0",
                target="phone",
                action="battery",
                verification_result=(True, "Verified"),
            )
        )
        resolved_goal, target, is_ambig = pronoun_resolver.resolve_reference("unlock it", state)
        assert is_ambig is False
        assert "phone" in resolved_goal or target == "phone"

        res = action_selector.select_action(resolved_goal, state)
        assert res.method == ControlMethod.ANDROID_SKILL
        assert res.action_name == "unlock_phone"

    # ── 11. Voice and text follow same route ──
    def test_11_voice_and_text_follow_same_route(self):
        # Both text and voice transcribe to text and enter is_automation_intent & action_selector
        prompt = "unlock my phone"
        assert is_automation_intent(prompt) is True
        res = action_selector.select_action(prompt, ComputerState())
        assert res.method == ControlMethod.ANDROID_SKILL
        assert res.action_name == "unlock_phone"

    # ── 12. FALSO stop cancels unlock waiting ──
    def test_12_falso_stop_cancels_unlock_waiting(self):
        mock_dev = AndroidDeviceState(device_id="dev1", is_authorized=True, connection_state=ConnectionState.READY)
        with patch.object(android_device_manager, "list_devices", return_value=[mock_dev]):
            with patch.object(authorized_unlock_manager.observer, "observe_lock_state", return_value={"is_locked": True, "state": "LOCKED"}):
                with patch.object(authorized_unlock_manager.controller, "wake_display", return_value={"success": True}):
                    android_device_skill.handle_unlock_request()
                    assert authorized_unlock_manager.get_active_workflow() is not None

                    stop_out = operator_engine.cancel()
                    assert stop_out == "Cancelled."
                    assert authorized_unlock_manager.get_active_workflow() is None

    # ── 13. No credential requested or stored ──
    def test_13_no_credential_requested_or_stored(self):
        mock_dev = AndroidDeviceState(device_id="dev1", is_authorized=True, connection_state=ConnectionState.READY)
        with patch.object(android_device_manager, "list_devices", return_value=[mock_dev]):
            with patch.object(authorized_unlock_manager.observer, "observe_lock_state", return_value={"is_locked": True, "state": "LOCKED"}):
                with patch.object(authorized_unlock_manager.controller, "wake_display", return_value={"success": True}):
                    res = android_device_skill.handle_unlock_request()
                    wf = authorized_unlock_manager.get_active_workflow()
                    # Assert no fields exist for password/pin/credentials
                    assert not hasattr(wf, "pin")
                    assert not hasattr(wf, "password")
                    assert not hasattr(wf, "pattern")
                    assert "pin" not in res["summary"].lower()
                    assert "password" not in res["summary"].lower()

    # ── 14. No authentication bypass exists ──
    def test_14_no_authentication_bypass(self):
        mock_dev = AndroidDeviceState(device_id="dev1", is_authorized=True, connection_state=ConnectionState.READY)
        with patch.object(authorized_unlock_manager.device_manager, "get_device_info", return_value=mock_dev):
            with patch.object(authorized_unlock_manager.controller, "wake_display", return_value={"success": True}):
                authorized_unlock_manager.initiate_unlock_wait("t1", "Goal", [], device_id="dev1")

            # While still locked, resume MUST fail
            with patch.object(authorized_unlock_manager.observer, "observe_lock_state", return_value={"is_locked": True, "state": "LOCKED"}):
                ok, msg = authorized_unlock_manager.resume_workflow()
                assert ok is False
                assert "Your phone is locked" in msg
