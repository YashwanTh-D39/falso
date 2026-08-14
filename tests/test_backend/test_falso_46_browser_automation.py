"""
Unit tests for FALSO 4.6 Advanced Browser Automation Foundation.
"""

import pytest
from unittest.mock import patch

from app.services.automation.browser.browser_action_registry import (
    ActionRiskLevel,
    StructuredBrowserAction,
    browser_action_registry,
)
from app.services.automation.browser.browser_engine import browser_engine
from app.services.automation.browser.element_targeter import element_targeter
from app.services.automation.browser.page_observation import (
    ElementRole,
    ElementSnapshot,
    PageObserver,
    page_observer,
)
from app.services.automation.permissions import FileOperation, permission_manager


class TestFalso46BrowserAutomation:

    def setup_method(self):
        permission_manager.disable_lockdown()
        browser_engine.current_snapshot = page_observer.observe_page()

    def teardown_method(self):
        permission_manager.disable_lockdown()
        browser_engine.current_snapshot = page_observer.observe_page()

    def test_01_open_browser(self):
        act = browser_action_registry.resolve_natural_language_action("open chrome")
        assert act is not None
        assert act.action == "open_browser"
        with patch("app.services.automation.windows.browser_controller.browser_controller.open_browser", return_value=True):
            res = browser_engine.execute_browser_action(act)
            assert res["success"] is True

    def test_02_new_tab(self):
        act = browser_action_registry.resolve_natural_language_action("open a new tab")
        assert act is not None
        assert act.action == "new_tab"
        with patch("app.services.automation.windows.in_app_action_engine.in_app_action_engine.execute_in_app_action", return_value={"success": True, "executed": True, "verified": True, "verification_reason": "New tab opened."}):
            res = browser_engine.execute_browser_action(act)
            assert res["success"] is True

    def test_03_navigate(self):
        act = browser_action_registry.resolve_natural_language_action("go to github.com")
        assert act is not None
        assert act.action == "navigate"
        assert "github.com" in act.target
        with patch("app.services.automation.windows.browser_controller.browser_controller.open_browser", return_value=True):
            res = browser_engine.execute_browser_action(act)
            assert res["success"] is True

    def test_04_back(self):
        act = StructuredBrowserAction(action="back", capability="browser.interact")
        with patch("app.services.automation.windows.in_app_action_engine.in_app_action_engine.execute_in_app_action", return_value={"success": True, "executed": True, "verified": True, "verification_reason": "Went back."}):
            res = browser_engine.execute_browser_action(act)
            assert res["success"] is True

    def test_05_forward(self):
        act = StructuredBrowserAction(action="forward", capability="browser.interact")
        with patch("app.services.automation.windows.in_app_action_engine.in_app_action_engine.execute_in_app_action", return_value={"success": True, "executed": True, "verified": True, "verification_reason": "Went forward."}):
            res = browser_engine.execute_browser_action(act)
            assert res["success"] is True

    def test_06_refresh(self):
        act = StructuredBrowserAction(action="refresh", capability="browser.interact")
        with patch("app.services.automation.windows.in_app_action_engine.in_app_action_engine.execute_in_app_action", return_value={"success": True, "executed": True, "verified": True, "verification_reason": "Refreshed."}):
            res = browser_engine.execute_browser_action(act)
            assert res["success"] is True

    def test_07_search(self):
        act = browser_action_registry.resolve_natural_language_action("search Google for CCNA courses")
        assert act is not None
        assert act.action == "search"
        with patch("app.services.automation.windows.browser_controller.browser_controller.search", return_value=True):
            res = browser_engine.execute_browser_action(act)
            assert res["success"] is True

    def test_08_find_element(self):
        elem = ElementSnapshot(role=ElementRole.BUTTON, name="Search", label="Search Button")
        snap = page_observer.observe_page(url="https://google.com", title="Google", elements=[elem])
        found = element_targeter.find_target_element(snap, "Search")
        assert found is not None
        assert found.name == "Search"

    def test_09_click_element(self):
        elem = ElementSnapshot(role=ElementRole.BUTTON, name="Search")
        browser_engine.current_snapshot = page_observer.observe_page(elements=[elem])
        act = StructuredBrowserAction(action="click", target="Search", capability="browser.interact")
        res = browser_engine.execute_browser_action(act)
        assert res["success"] is True

    def test_10_scroll(self):
        act = browser_action_registry.resolve_natural_language_action("scroll down")
        assert act is not None
        assert act.action == "scroll"
        with patch("app.services.automation.windows.in_app_action_engine.in_app_action_engine.execute_in_app_action", return_value={"success": True, "executed": True, "verified": True, "verification_reason": "Scrolled."}):
            res = browser_engine.execute_browser_action(act)
            assert res["success"] is True

    def test_11_read_page(self):
        browser_engine.current_snapshot = page_observer.observe_page(title="Example Domain")
        act = browser_action_registry.resolve_natural_language_action("tell me page title")
        assert act is not None
        res = browser_engine.execute_browser_action(act)
        assert res["success"] is True
        assert "Example Domain" in res["result_text"]

    def test_12_detect_form(self):
        from app.services.automation.browser.form_manager import form_manager
        elem = ElementSnapshot(role=ElementRole.TEXTBOX, name="Email", label="Email Address")
        snap = page_observer.observe_page(elements=[elem])
        forms = form_manager.detect_forms(snap)
        assert len(forms) > 0
        assert forms[0].fields[0].label == "Email Address"

    def test_13_map_form_fields(self):
        from app.services.automation.browser.form_manager import form_manager
        elem = ElementSnapshot(role=ElementRole.TEXTBOX, name="Full Name", label="Full Name", element_id="name_id")
        snap = page_observer.observe_page(elements=[elem])
        form = form_manager.detect_forms(snap)[0]
        mapped = form_manager.map_user_input_to_fields(form, {"name": "Yashwanth"})
        assert mapped.get("name_id") == "Yashwanth"

    def test_14_fill_safe_form(self):
        from app.services.automation.browser.form_manager import form_manager
        elem = ElementSnapshot(role=ElementRole.TEXTBOX, name="Full Name", label="Full Name", element_id="name_id")
        snap = page_observer.observe_page(elements=[elem])
        form = form_manager.detect_forms(snap)[0]
        fill_res = form_manager.fill_and_verify_form(form, {"name_id": "Yashwanth"})
        assert fill_res.success is True

    def test_15_sensitive_field_protection(self):
        from app.services.automation.browser.form_manager import form_manager
        is_sens = form_manager.is_sensitive_field("Password", "password")
        assert is_sens is True

    def test_16_captcha_detection(self):
        snap = page_observer.observe_page(visible_text="Please solve this reCAPTCHA to continue")
        assert snap.has_captcha is True
        browser_engine.current_snapshot = snap
        act = StructuredBrowserAction(action="click", target="Submit", capability="browser.interact")
        res = browser_engine.execute_browser_action(act)
        assert res["success"] is False
        assert "CAPTCHA" in res["verification_reason"]

    def test_17_submission_confirmation(self):
        act = browser_action_registry.resolve_natural_language_action("submit form")
        assert act is not None
        assert act.requires_confirmation is True
        res = browser_engine.execute_browser_action(act)
        assert "ready to submit" in res["result_text"]

    def test_18_submission_verification(self):
        from app.services.automation.browser.form_manager import form_manager
        elem = ElementSnapshot(role=ElementRole.TEXTBOX, name="Name", label="Name", element_id="name")
        snap = page_observer.observe_page(elements=[elem])
        form = form_manager.detect_forms(snap)[0]
        fill_res = form_manager.fill_and_verify_form(form, {"name": "Yashwanth"})
        assert fill_res.verified_fields.get("Name") is True

    def test_19_multi_step_browser_workflow(self):
        from app.services.automation.goal_planner import goal_planner
        plan = goal_planner.create_plan("Open Chrome, create a new tab, go to github.com")
        assert len(plan.steps) >= 2

    def test_20_session_context(self):
        from app.services.session_history import session_history_manager
        session_history_manager.append_user_message("SESS-1", "Open Chrome")
        session_history_manager.append_assistant_message("SESS-1", "Chrome is open.")
        last_app = session_history_manager.get_last_target_app("SESS-1")
        assert last_app == "Chrome"

    def test_21_browser_action_cancellation(self):
        from app.services.automation.autopilot import autopilot_agent
        autopilot_agent.cancel_active_task()
        assert autopilot_agent.active_task is None

    def test_22_permission_enforcement(self):
        permission_manager.enable_lockdown()
        act = StructuredBrowserAction(action="navigate", target="https://google.com", capability="browser.navigate")
        res = browser_engine.execute_browser_action(act)
        assert res["success"] is False
        assert "Lockdown" in res["verification_reason"]

    def test_23_arbitrary_shell_denied(self):
        check = permission_manager.check_command_execution("powershell.exe -Command Remove-Item C:\\Windows")
        assert check.allowed is False

    def test_24_credential_extraction_denied(self):
        check = permission_manager.check_filesystem_access("C:\\Users\\Admin\\.env", operation=FileOperation.READ)
        assert check.allowed is False

    def test_25_download_execution_denied(self):
        check = permission_manager.check_filesystem_access("C:\\Windows\\System32\\cmd.exe", operation=FileOperation.EXECUTE)
        assert check.allowed is False
