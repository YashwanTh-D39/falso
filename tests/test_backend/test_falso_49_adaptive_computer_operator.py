"""
FALSO 4.9 Adaptive Computer Operator Engine Tests.

Tests:
1. ComputerState & EvidenceType classifications (OBSERVED, INFERRED, UNKNOWN)
2. ComputerObserver hierarchy and bounded state-based waits
3. ActionSelector control method preference and honest failure on unidentifiable targets
4. PronounResolver reference resolution and ambiguity safety
5. Application Skills (Calculator, Notepad, Chrome, Explorer, VS Code)
6. Controlled Cybersecurity Skill scope enforcement
7. SkillRegistry registration & lookup
8. Action Idempotency
9. Multi-step task execution
10. Interruption and cancellation ("FALSO stop")
11. False-success prevention
12. Verified Action History privacy and recording
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch
import pytest

from app.services.automation.operator.action_selector import ControlMethod, action_selector
from app.services.automation.operator.computer_observer import computer_observer
from app.services.automation.operator.computer_state import (
    BrowserStateInfo,
    ComputerState,
    EvidenceType,
    StateValue,
    UIElementInfo,
    VerifiedActionRecord,
    WindowInfo,
)
from app.services.automation.operator.operator_engine import operator_engine
from app.services.automation.operator.pronoun_resolver import pronoun_resolver
from app.services.automation.operator.skills.calculator_skill import CalculatorSkill
from app.services.automation.operator.skills.chrome_skill import ChromeSkill
from app.services.automation.operator.skills.cybersecurity_skill import CybersecuritySkill
from app.services.automation.operator.skills.explorer_skill import ExplorerSkill
from app.services.automation.operator.skills.notepad_skill import NotepadSkill
from app.services.automation.operator.skills.skill_registry import skill_registry
from app.services.automation.operator.skills.vscode_skill import VSCodeSkill
from app.services.automation.windows.process_manager import process_manager
from app.services.automation.windows.ui_automation import ui_automation
from app.services.automation.windows.window_manager import window_manager


class TestFalso49AdaptiveComputerOperator:
    # ── 1. ComputerState & EvidenceType ──
    def test_01_computer_state_evidence_classification(self):
        state = ComputerState()
        # Default state values are UNKNOWN
        assert state.foreground_window.is_unknown()
        assert not state.foreground_window.is_observed()

        # Set OBSERVED value
        w_info = WindowInfo(hwnd=101, title="Calculator", is_foreground=True)
        state.foreground_window = StateValue(value=w_info, evidence=EvidenceType.OBSERVED, source="test")
        assert state.foreground_window.is_observed()
        assert state.foreground_window.value.title == "Calculator"

        # Test INFERRED cannot alone prove verified
        val_inferred = StateValue(value="Chrome", evidence=EvidenceType.INFERRED, source="planner")
        assert val_inferred.is_inferred()
        assert not val_inferred.is_observed()

    def test_02_verified_action_history_recording(self):
        state = ComputerState()
        rec = VerifiedActionRecord(
            task_id="t-1",
            action_id="a-1",
            target="Calculator",
            action="calculate",
            verification_result=(True, "Verified 20"),
            safe_summary="calculate on Calculator",
        )
        state.add_verified_action(rec)
        assert len(state.verified_action_history) == 1
        assert state.get_last_verified_target() == "Calculator"
        assert state.last_verified_action.is_observed()

    # ── 2. ComputerObserver & Bounded Waits ──
    def test_03_computer_observer_hierarchical_observation(self):
        with patch.object(window_manager, "get_active_window", return_value={"hwnd": 202, "title": "Notepad", "process_id": 1234}), \
             patch.object(window_manager, "list_windows", return_value=[{"hwnd": 202, "title": "Notepad", "process_id": 1234, "process_name": "notepad.exe"}]), \
             patch.object(window_manager, "is_window_open", side_effect=lambda name: name.lower() == "notepad"):
            state = computer_observer.observe()
            assert state.foreground_window.is_observed()
            assert state.foreground_window.value.title == "Notepad"
            assert state.foreground_application.value == "Notepad"
            assert state.is_app_open("Notepad")

    def test_04_computer_observer_bounded_waits(self):
        with patch.object(window_manager, "is_window_open", side_effect=[False, False, True]):
            ok = computer_observer.wait_for_window("Calculator", timeout=1.0, poll_interval=0.01)
            assert ok is True

        with patch.object(window_manager, "verify_foreground", return_value=False):
            fail = computer_observer.wait_for_foreground("Chrome", timeout=0.05, poll_interval=0.01)
            assert fail is False

    # ── 3. ActionSelector ──
    def test_05_action_selector_routing(self):
        state = ComputerState()
        # Open app intent
        res_open = action_selector.select_action("Open Chrome", state)
        assert res_open.method == ControlMethod.WINDOW_MANAGER
        assert res_open.target_app == "Chrome"

        # Math intent -> Application Skill
        res_calc = action_selector.select_action("Calculate 25 * 4", state)
        assert res_calc.method == ControlMethod.APPLICATION_SKILL
        assert res_calc.target_app == "Calculator"

        # Web navigation intent -> Browser Automation
        res_nav = action_selector.select_action("Navigate to https://github.com", state)
        assert res_nav.method == ControlMethod.BROWSER_AUTOMATION
        assert res_nav.params["url"] == "https://github.com"

    def test_06_action_selector_refuses_to_guess_unidentifiable_elements(self):
        state = ComputerState()
        with patch.object(ui_automation, "is_available", return_value=True), \
             patch.object(ui_automation, "find_element", return_value=None):
            res_click = action_selector.select_action("Click non_existent_mystery_button", state)
            assert res_click.method == ControlMethod.UNAVAILABLE
            assert res_click.confidence == 0.0
            assert "Refusing to guess" in res_click.reasoning

    # ── 4. PronounResolver ──
    def test_07_pronoun_resolver_from_verified_history(self):
        state = ComputerState()
        rec = VerifiedActionRecord(
            task_id="t-1",
            action_id="a-1",
            target="Calculator",
            action="open",
            verification_result=(True, "Verified"),
        )
        state.add_verified_action(rec)

        resolved_prompt, target, is_ambiguous = pronoun_resolver.resolve_reference("Close it", state)
        assert is_ambiguous is False
        assert target == "Calculator"
        assert "Calculator" in resolved_prompt

    def test_08_pronoun_resolver_ambiguity_protection(self):
        state = ComputerState()
        # No history, no foreground app
        resolved_prompt, target, is_ambiguous = pronoun_resolver.resolve_reference("Close it", state)
        assert is_ambiguous is True
        assert target is None

    # ── 5. Application Skills ──
    def test_09_calculator_skill_lifecycle(self):
        skill = CalculatorSkill()
        state = ComputerState()
        with patch.object(process_manager, "launch_app", return_value={"success": True, "verified": True}), \
             patch.object(window_manager, "verify_foreground", return_value=True), \
             patch.object(window_manager, "is_window_open", return_value=True):
            res = skill.execute("open", "Calculator", {}, state)
            assert res["success"] is True
            state.approved_running_applications = StateValue(value=["Calculator"], evidence=EvidenceType.OBSERVED)
            verified, reason = skill.verify("open", "Calculator", state, state, res)
            assert verified is True

    def test_10_notepad_skill_typing_and_clipboard(self):
        skill = NotepadSkill()
        state = ComputerState()
        with patch("app.services.automation.operator.skills.notepad_skill.in_app_action_engine.execute_in_app_action", return_value={"success": True, "verified": True, "reason": "Text verified"}), \
             patch("app.services.automation.operator.skills.notepad_skill.clipboard_controller.has_text", return_value=True):
            res_type = skill.execute("type", "Notepad", {"text": "hello"}, state)
            verified, reason = skill.verify("type", "Notepad", state, state, res_type)
            assert verified is True

            res_copy = skill.execute("copy", "Notepad", {}, state)
            verified_copy, _ = skill.verify("copy", "Notepad", state, state, res_copy)
            assert verified_copy is True

    def test_11_chrome_skill_navigation_and_tabs(self):
        skill = ChromeSkill()
        state = ComputerState()
        with patch("app.services.automation.operator.skills.chrome_skill.in_app_action_engine.execute_in_app_action", return_value={"success": True, "verified": True, "reason": "Tab verified"}):
            res_tab = skill.execute("new_tab", "Chrome", {}, state)
            verified, _ = skill.verify("new_tab", "Chrome", state, state, res_tab)
            assert verified is True

    def test_12_explorer_skill_navigation(self):
        skill = ExplorerSkill()
        state = ComputerState()
        with patch("app.services.automation.operator.skills.explorer_skill.in_app_action_engine.execute_in_app_action", return_value={"success": True, "verified": True, "reason": "Folder opened"}):
            res = skill.execute("navigate_folder", "Explorer", {"folder": "C:\\Users"}, state)
            verified, _ = skill.verify("navigate_folder", "Explorer", state, state, res)
            assert verified is True

    def test_13_vscode_skill_test_execution(self):
        skill = VSCodeSkill()
        state = ComputerState()
        res = skill.execute("run_tests", "VS Code", {}, state)
        assert res["success"] is True
        verified, reason = skill.verify("run_tests", "VS Code", state, state, res)
        assert verified is True

    # ── 6. Cybersecurity Readiness ──
    def test_14_cybersecurity_skill_scope_enforcement(self):
        skill = CybersecuritySkill()
        state = ComputerState()
        # Localhost port check -> ALLOWED
        with patch.object(skill, "_check_port_open", return_value=True):
            res_local = skill.execute("port_check", "security", {"host": "127.0.0.1", "port": 8080}, state)
            assert res_local["success"] is True
            assert res_local["is_open"] is True

        # Unauthorized remote host -> DENIED
        res_remote = skill.execute("port_check", "security", {"host": "192.168.1.100", "port": 443}, state)
        assert res_remote["success"] is False
        assert res_remote.get("denied") is True

    # ── 7. SkillRegistry ──
    def test_15_skill_registry_lookup(self):
        calc_skill = skill_registry.find_skill("Calculator", "calculate")
        assert calc_skill is not None
        assert calc_skill.name == "calculator"

        chrome_skill = skill_registry.find_skill("Chrome", "new_tab")
        assert chrome_skill is not None
        assert chrome_skill.name == "chrome"

    # ── 8. Action Idempotency ──
    @pytest.mark.asyncio
    async def test_16_action_idempotency_skips_redundant_app_launch(self):
        state = ComputerState()
        w_info = WindowInfo(hwnd=303, title="Calculator", is_foreground=True)
        state.foreground_window = StateValue(value=w_info, evidence=EvidenceType.OBSERVED)
        state.visible_windows = StateValue(value=[w_info], evidence=EvidenceType.OBSERVED)

        with patch.object(operator_engine.observer, "observe", return_value=state), \
             patch.object(window_manager, "focus_window", return_value=True) as mock_focus:
            resp = await operator_engine.run_operation("Open Calculator")
            assert resp == "Done."
            # Idempotency brought window to focus without spawning second instance
            mock_focus.assert_called_with("Calculator")

    # ── 9. Multi-Step Execution & Verification ──
    @pytest.mark.asyncio
    async def test_17_multi_step_operator_workflow(self):
        with patch.object(process_manager, "launch_app", return_value={"success": True, "verified": True}), \
             patch.object(window_manager, "verify_foreground", return_value=True), \
             patch.object(window_manager, "is_window_open", return_value=True), \
             patch("app.services.automation.operator.skills.calculator_skill.in_app_action_engine.execute_in_app_action", return_value={"success": True, "verified": True, "actual_result": 20, "reason": "Calculated 20"}):
            resp = await operator_engine.run_operation("Open Calculator then calculate 10 + 10")
            assert resp == "20"

    # ── 10. Interruption ("FALSO stop") ──
    @pytest.mark.asyncio
    async def test_18_operator_interruption_falso_stop(self):
        cancel_resp = operator_engine.cancel()
        assert cancel_resp == "Cancelled."
        assert not operator_engine.is_active()

    # ── 11. False-Success Prevention ──
    @pytest.mark.asyncio
    async def test_19_verification_failure_never_returns_done(self):
        state = ComputerState()
        with patch.object(operator_engine.observer, "observe", return_value=state), \
             patch.object(process_manager, "launch_app", return_value={"success": False, "verified": False}), \
             patch.object(window_manager, "verify_foreground", return_value=False):
            resp = await operator_engine.run_operation("Open Chrome")
            assert resp != "Done."
            assert "couldn't" in resp.lower() or "failed" in resp.lower()
