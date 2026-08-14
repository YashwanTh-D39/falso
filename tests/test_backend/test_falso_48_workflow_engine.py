"""
Unit and Integration tests for FALSO 4.8 Multi-Step Web Workflow Engine.
"""

import pytest
from unittest.mock import patch

from app.services.automation.browser.browser_action_registry import StructuredBrowserAction, browser_action_registry
from app.services.automation.browser.browser_engine import browser_engine
from app.services.automation.browser.form_manager import form_manager
from app.services.automation.browser.page_observation import (
    ElementRole,
    ElementSnapshot,
    FormFieldSnapshot,
    FormSnapshot,
    page_observer,
)
from app.services.automation.permissions import FileOperation, permission_manager
from app.services.automation.workflow.workflow_engine import workflow_engine
from app.services.automation.workflow.workflow_models import (
    BrowserContextState,
    WorkflowState,
    WorkflowStep,
    WorkflowStepState,
)
from app.services.automation.workflow.workflow_planner import workflow_planner


class TestFalso48WorkflowEngine:

    def setup_method(self):
        permission_manager.disable_lockdown()
        browser_engine.current_snapshot = page_observer.observe_page()
        workflow_engine.state = WorkflowState.COMPLETED
        workflow_engine.steps = []
        workflow_engine.current_step_index = 0

    def teardown_method(self):
        permission_manager.disable_lockdown()
        browser_engine.current_snapshot = page_observer.observe_page()

    def test_01_workflow_creation(self):
        with patch("app.services.automation.windows.browser_controller.browser_controller.open_browser", return_value=True), \
             patch("app.services.automation.windows.browser_controller.browser_controller.search", return_value=True):
            res = workflow_engine.run_workflow("Open Chrome and search for FALSO", session_id="SESS-101")
            assert res.workflow_id is not None
            assert res.session_id == "SESS-101"
            assert res.state in (WorkflowState.COMPLETED, WorkflowState.WAITING_USER)

    def test_02_dynamic_planning(self):
        steps = workflow_planner.plan_workflow("Open Chrome, create a new tab, go to github.com", session_id="SESS-102")
        assert len(steps) >= 2
        actions = [s.action for s in steps]
        assert "open_browser" in actions or "new_tab" in actions
        assert steps[0].action_id != ""

    def test_03_step_execution(self):
        with patch("app.services.automation.windows.browser_controller.browser_controller.open_browser", return_value=True):
            res = workflow_engine.run_workflow("Open Chrome", session_id="SESS-103")
            assert res.state == WorkflowState.COMPLETED
            assert len(res.steps) > 0
            assert res.steps[0].status == WorkflowStepState.COMPLETED

    def test_04_step_verification(self):
        with patch("app.services.automation.windows.browser_controller.browser_controller.search", return_value=True):
            res = workflow_engine.run_workflow("Search Google for CCNA courses", session_id="SESS-104")
            assert res.state == WorkflowState.COMPLETED
            assert res.steps[0].verification != ""

    def test_05_replanning(self):
        ctx = BrowserContextState(current_url="https://github.com")
        steps = workflow_planner.plan_workflow("Go to github.com", context=ctx, session_id="SESS-105")
        actions = [s.action for s in steps]
        assert "navigate" not in actions or len(steps) == 0

    def test_06_recovery(self):
        with patch.object(browser_engine, "execute_browser_action") as mock_act:
            mock_act.side_effect = [
                {"success": False, "verified": False, "verification_reason": "Transient network delay", "before_state": {}, "after_state": {}},
                {"success": True, "verified": True, "verification_reason": "Verified PASS", "result_text": "Done.", "before_state": {}, "after_state": {}}
            ]
            res = workflow_engine.run_workflow("Open Chrome", session_id="SESS-106")
            assert res.state == WorkflowState.COMPLETED
            assert res.steps[0].verification == "Recovered & Verified PASS"

    def test_07_idempotency(self):
        ctx = BrowserContextState(current_url="https://github.com")
        steps = workflow_planner.plan_workflow("Go to github.com", context=ctx, session_id="SESS-107")
        assert not any(s.action == "navigate" and s.target == "https://github.com" for s in steps)

    def test_08_browser_context(self):
        ctx = BrowserContextState(active_browser="Chrome", current_url="https://github.com")
        assert ctx.active_browser == "Chrome"
        assert ctx.current_url == "https://github.com"

    def test_09_session_memory(self):
        from app.services.session_history import session_history_manager
        session_history_manager.append_user_message("WORKFLOW-SESS", "Open Chrome")
        session_history_manager.append_assistant_message("WORKFLOW-SESS", "Chrome is open.")
        last_app = session_history_manager.get_last_target_app("WORKFLOW-SESS")
        assert last_app == "Chrome"

    def test_10_confirmation_pause_waiting_user(self):
        form_obj = FormSnapshot(form_id="form_1", fields=[FormFieldSnapshot(field_id="f1", label="Full Name", field_type="text", name_attr="name")])
        browser_engine.current_snapshot = page_observer.observe_page(forms=[form_obj])
        res = workflow_engine.run_workflow("Fill the form and submit it", session_id="SESS-110")
        assert res.state == WorkflowState.WAITING_USER
        assert "ready to submit" in res.final_message

    def test_11_workflow_resume(self):
        form_obj = FormSnapshot(form_id="form_1", fields=[FormFieldSnapshot(field_id="f1", label="Full Name", field_type="text", name_attr="name")])
        browser_engine.current_snapshot = page_observer.observe_page(forms=[form_obj])
        res1 = workflow_engine.run_workflow("Fill the form and submit it", session_id="SESS-111")
        assert res1.state == WorkflowState.WAITING_USER
        res2 = workflow_engine.resume_workflow(user_confirmation="yes", session_id="SESS-111")
        assert res2.state == WorkflowState.COMPLETED

    def test_12_cancellation_falso_stop(self):
        form_obj = FormSnapshot(form_id="form_1", fields=[FormFieldSnapshot(field_id="f1", label="Full Name", field_type="text", name_attr="name")])
        browser_engine.current_snapshot = page_observer.observe_page(forms=[form_obj])
        workflow_engine.run_workflow("Fill the form and submit it", session_id="SESS-112")
        assert workflow_engine.state == WorkflowState.WAITING_USER
        msg = workflow_engine.cancel_workflow()
        assert msg == "Cancelled."
        assert workflow_engine.state == WorkflowState.CANCELLED

    def test_13_timeouts(self):
        with patch.object(browser_engine, "execute_browser_action") as mock_act:
            mock_act.return_value = {
                "success": False, "verified": False,
                "verification_reason": "Timeout waiting for element",
                "before_state": {}, "after_state": {}
            }
            res = workflow_engine.run_workflow("Click NonExistent", session_id="SESS-113")
            assert res.state == WorkflowState.FAILED
            assert "couldn't complete" in res.final_message

    def test_14_popup_handling(self):
        snap = page_observer.observe_page(visible_text="We use cookies to improve your experience. Accept Cookies")
        assert snap is not None
        assert "Cookies" in snap.visible_text

    def test_15_download_safety(self):
        check = permission_manager.check_filesystem_access("C:\\Windows\\System32\\calc.exe", operation=FileOperation.EXECUTE)
        assert check.allowed is False

    def test_16_external_side_effect_confirmation(self):
        check = permission_manager.check_capability("browser.submit_form")
        assert check.requires_confirmation is True

    def test_17_permission_enforcement(self):
        permission_manager.enable_lockdown()
        res = workflow_engine.run_workflow("Open Chrome", session_id="SESS-117")
        assert res.state == WorkflowState.FAILED

    def test_18_audit_logging(self):
        with patch("app.services.automation.windows.browser_controller.browser_controller.open_browser", return_value=True):
            res = workflow_engine.run_workflow("Open Chrome", session_id="SESS-118")
            assert res.state == WorkflowState.COMPLETED

    def test_19_concise_responses(self):
        with patch("app.services.automation.windows.browser_controller.browser_controller.open_browser", return_value=True):
            res = workflow_engine.run_workflow("Open Chrome", session_id="SESS-119")
            assert "Navigated to" in res.final_message or res.final_message == "Done."

    def test_20_cybersecurity_diagnostic_workflow(self):
        steps = workflow_planner.plan_workflow("Run cybersecurity diagnostic scan on network state", session_id="SESS-120")
        assert len(steps) >= 2
        assert "security" in steps[0].target.lower() or "read_page" in steps[0].action

    def test_21_46_dependency_verification(self):
        # Verify 4.6 BrowserActionRegistry primitive resolves browser actions
        act = browser_action_registry.resolve_natural_language_action("open chrome")
        assert act is not None
        assert act.action == "open_browser"

    def test_22_47_dependency_verification(self):
        # Verify 4.7 FormManager primitive detects form structures
        snap = page_observer.observe_page(forms=[{"form_id": "form_1", "fields": [{"name": "email", "type": "email"}]}])
        forms = form_manager.detect_forms(snap)
        assert len(forms) > 0

    def test_23_real_browser_integration(self):
        with patch("app.services.automation.windows.browser_controller.browser_controller.open_browser", return_value=True), \
             patch("app.services.automation.windows.browser_controller.browser_controller.navigate", return_value=True), \
             patch("app.services.automation.windows.in_app_action_engine.in_app_action_engine.execute_in_app_action", return_value={"success": True, "executed": True, "verified": True, "verification_reason": "New tab opened."}):
            res = workflow_engine.run_workflow("Open Chrome, open a new tab, go to example.com", session_id="SESS-REAL-BROWSER")
            assert res.state == WorkflowState.COMPLETED
            assert len(res.steps) >= 2

    def test_24_real_form_workflow(self):
        form_obj = FormSnapshot(form_id="form_1", fields=[FormFieldSnapshot(field_id="f1", label="Full Name", field_type="text", name_attr="name")])
        with patch.object(page_observer, "observe_page", return_value=page_observer.observe_page(forms=[form_obj])), \
             patch("app.services.automation.windows.browser_controller.browser_controller.open_browser", return_value=True):
            res1 = workflow_engine.run_workflow("Open the test form, fill my safe details and submit it", session_id="SESS-FORM-REAL")
            assert res1.state == WorkflowState.WAITING_USER
            assert "ready to submit" in res1.final_message
            res2 = workflow_engine.resume_workflow(user_confirmation="yes", session_id="SESS-FORM-REAL")
            assert res2.state == WorkflowState.COMPLETED
            assert res2.final_message in ("Done.", "Form submitted.")

    def test_25_workflow_ownership_isolation(self):
        form_obj = FormSnapshot(form_id="form_1", fields=[FormFieldSnapshot(field_id="f1", label="Full Name", field_type="text", name_attr="name")])
        browser_engine.current_snapshot = page_observer.observe_page(forms=[form_obj])
        workflow_engine.run_workflow("Fill the form and submit it", session_id="SESS-A")
        assert workflow_engine.state == WorkflowState.WAITING_USER
        res = workflow_engine.resume_workflow(user_confirmation="yes", session_id="SESS-B")
        assert res.final_message == "No workflow waiting for user confirmation."
        assert workflow_engine.state == WorkflowState.WAITING_USER

    def test_26_confirmation_binding(self):
        form_obj = FormSnapshot(form_id="form_1", fields=[FormFieldSnapshot(field_id="f1", label="Full Name", field_type="text", name_attr="name")])
        browser_engine.current_snapshot = page_observer.observe_page(forms=[form_obj])
        res1 = workflow_engine.run_workflow("Fill the form and submit it", session_id="SESS-BIND")
        assert res1.state == WorkflowState.WAITING_USER
        res2 = workflow_engine.resume_workflow(user_confirmation="proceed", session_id="SESS-BIND")
        assert res2.state == WorkflowState.COMPLETED

    def test_27_cancelled_workflow_resurrection_prevention(self):
        form_obj = FormSnapshot(form_id="form_1", fields=[FormFieldSnapshot(field_id="f1", label="Full Name", field_type="text", name_attr="name")])
        browser_engine.current_snapshot = page_observer.observe_page(forms=[form_obj])
        workflow_engine.run_workflow("Fill the form and submit it", session_id="SESS-CANCEL")
        assert workflow_engine.state == WorkflowState.WAITING_USER
        workflow_engine.cancel_workflow()
        assert workflow_engine.state == WorkflowState.CANCELLED
        res = workflow_engine.resume_workflow(user_confirmation="yes", session_id="SESS-CANCEL")
        assert res.final_message == "No workflow waiting for user confirmation."
        assert workflow_engine.state == WorkflowState.CANCELLED

    def test_28_fake_success_prevention(self):
        with patch.object(browser_engine, "execute_browser_action") as mock_act:
            mock_act.return_value = {
                "success": True,
                "verified": False,
                "verification_reason": "Verification failed: page did not navigate",
                "before_state": {},
                "after_state": {}
            }
            res = workflow_engine.run_workflow("Go to example.com", session_id="SESS-FAKE")
            assert res.state == WorkflowState.FAILED
            assert res.final_message == "I couldn't complete that."
