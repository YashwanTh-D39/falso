"""
Unit tests for FALSO 4.7 Intelligent Web Form Automation.
"""

import pytest
from app.services.automation.browser.browser_engine import browser_engine
from app.services.automation.browser.form_manager import (
    FormFillResult,
    FormFieldSnapshot,
    FormManager,
    FormSnapshot,
    form_manager,
)
from app.services.automation.browser.page_observation import (
    ElementRole,
    ElementSnapshot,
    PageObserver,
    page_observer,
)
from app.services.automation.permissions import FileOperation, permission_manager


class TestFalso47FormAutomation:

    def setup_method(self):
        permission_manager.disable_lockdown()

    def teardown_method(self):
        permission_manager.disable_lockdown()

    def test_01_form_detection(self):
        elem = ElementSnapshot(role=ElementRole.TEXTBOX, name="Full Name", label="Full Name", element_id="name")
        snap = page_observer.observe_page(elements=[elem])
        forms = form_manager.detect_forms(snap)
        assert len(forms) == 1
        assert forms[0].fields[0].label == "Full Name"

    def test_02_text_field_mapping(self):
        elem = ElementSnapshot(role=ElementRole.TEXTBOX, name="Full Name", label="Full Name", element_id="fname")
        snap = page_observer.observe_page(elements=[elem])
        form = form_manager.detect_forms(snap)[0]
        mapped = form_manager.map_user_input_to_fields(form, {"name": "Yashwanth"})
        assert mapped.get("fname") == "Yashwanth"

    def test_03_email_field_mapping(self):
        elem = ElementSnapshot(role=ElementRole.EMAIL, name="Email Address", label="Email Address", element_id="email_id")
        snap = page_observer.observe_page(elements=[elem])
        form = form_manager.detect_forms(snap)[0]
        mapped = form_manager.map_user_input_to_fields(form, {"email": "test@example.com"})
        assert mapped.get("email_id") == "test@example.com"

    def test_04_textarea(self):
        elem = ElementSnapshot(role=ElementRole.TEXTAREA, name="Comments", label="Comments", element_id="comments")
        snap = page_observer.observe_page(elements=[elem])
        form = form_manager.detect_forms(snap)[0]
        mapped = form_manager.map_user_input_to_fields(form, {"comments": "Hello FALSO"})
        assert mapped.get("comments") == "Hello FALSO"

    def test_05_dropdown(self):
        elem = ElementSnapshot(role=ElementRole.SELECT, name="Country", label="Country", options=["USA", "India"], element_id="country")
        snap = page_observer.observe_page(elements=[elem])
        form = form_manager.detect_forms(snap)[0]
        res = form_manager.fill_and_verify_form(form, {"country": "India"})
        assert res.success is True
        assert res.filled_fields["Country"] == "India"

    def test_06_checkbox(self):
        elem = ElementSnapshot(role=ElementRole.CHECKBOX, name="Accept Terms", label="Accept Terms", element_id="terms")
        snap = page_observer.observe_page(elements=[elem])
        form = form_manager.detect_forms(snap)[0]
        res = form_manager.fill_and_verify_form(form, {"terms": "true"})
        assert res.success is True

    def test_07_radio_button(self):
        elem = ElementSnapshot(role=ElementRole.RADIO, name="Gender", label="Male", element_id="male_radio")
        snap = page_observer.observe_page(elements=[elem])
        form = form_manager.detect_forms(snap)[0]
        res = form_manager.fill_and_verify_form(form, {"male_radio": "selected"})
        assert res.success is True

    def test_08_date_field_ambiguity(self):
        val, is_ambig, msg = form_manager.handle_date_field("10/11/2026")
        assert is_ambig is True
        assert "specify month and day" in msg

    def test_09_missing_required_information(self):
        fld = FormFieldSnapshot(field_id="email", label="Email", field_type="email", required=True)
        form = FormSnapshot(form_id="f1", name="Form", fields=[fld])
        res = form_manager.fill_and_verify_form(form, {})
        assert res.success is False
        assert "Email" in res.summary

    def test_10_ambiguous_field(self):
        val, is_ambig, msg = form_manager.handle_date_field("05/06/2026")
        assert is_ambig is True

    def test_11_safe_memory_retrieval(self):
        user_data = {"name": "Yashwanth", "email": "test@example.com"}
        fld = FormFieldSnapshot(field_id="name", label="Full Name", field_type="text")
        form = FormSnapshot(form_id="f1", name="Form", fields=[fld])
        mapped = form_manager.map_user_input_to_fields(form, user_data)
        assert mapped["name"] == "Yashwanth"

    def test_12_sensitive_field_detection(self):
        assert form_manager.is_sensitive_field("Password", "password") is True
        assert form_manager.is_sensitive_field("OTP Code", "text") is True
        assert form_manager.is_sensitive_field("Credit Card Number", "text") is True
        assert form_manager.is_sensitive_field("Full Name", "text") is False

    def test_13_secret_protection(self):
        fld = FormFieldSnapshot(field_id="pwd", label="Password", field_type="password", is_sensitive=True)
        form = FormSnapshot(form_id="f1", name="Form", fields=[fld])
        res = form_manager.fill_and_verify_form(form, {"pwd": "SecretPassword123"})
        assert res.filled_fields["Password"] == "******"

    def test_14_field_verification(self):
        fld = FormFieldSnapshot(field_id="name", label="Full Name", field_type="text")
        form = FormSnapshot(form_id="f1", name="Form", fields=[fld])
        res = form_manager.fill_and_verify_form(form, {"name": "Yashwanth"})
        assert res.verified_fields.get("Full Name") is True

    def test_15_form_summary(self):
        fld = FormFieldSnapshot(field_id="name", label="Full Name", field_type="text")
        form = FormSnapshot(form_id="f1", name="Form", fields=[fld], is_consequential=True)
        res = form_manager.fill_and_verify_form(form, {"name": "Yashwanth"})
        assert "ready to submit" in res.summary

    def test_16_submission_confirmation_gate(self):
        fld = FormFieldSnapshot(field_id="name", label="Full Name", field_type="text")
        form = FormSnapshot(form_id="f1", name="Form", fields=[fld], is_consequential=True)
        res = form_manager.fill_and_verify_form(form, {"name": "Yashwanth"})
        assert res.requires_submission_confirmation is True

    def test_17_submission_verification(self):
        fld = FormFieldSnapshot(field_id="name", label="Full Name", field_type="text")
        form = FormSnapshot(form_id="f1", name="Form", fields=[fld], is_consequential=False)
        res = form_manager.fill_and_verify_form(form, {"name": "Yashwanth"})
        assert res.requires_submission_confirmation is False

    def test_18_captcha_detection(self):
        snap = page_observer.observe_page(visible_text="Solve this CAPTCHA")
        assert snap.has_captcha is True

    def test_19_file_upload_restrictions(self):
        check = permission_manager.check_filesystem_access("C:\\Users\\Admin\\.env", operation=FileOperation.READ)
        assert check.allowed is False

    def test_20_session_context(self):
        from app.services.session_history import session_history_manager
        session_history_manager.append_user_message("SESS-FORM", "My name is Yashwanth.")
        hist = session_history_manager.get_history("SESS-FORM")
        assert len(hist) > 0
        assert hist[0].content == "My name is Yashwanth."

    def test_21_cancellation(self):
        from app.services.automation.autopilot import autopilot_agent
        resp = autopilot_agent.cancel_active_task()
        assert resp == "Cancelled."

    def test_22_permission_enforcement(self):
        permission_manager.enable_lockdown()
        fld = FormFieldSnapshot(field_id="name", label="Full Name", field_type="text")
        form = FormSnapshot(form_id="f1", name="Form", fields=[fld])
        res = form_manager.fill_and_verify_form(form, {"name": "Yashwanth"})
        assert res.success is False
        assert "denied" in res.summary.lower()
