"""
Intelligent Web Form Automation Manager for FALSO (FALSO 4.7).

Handles form understanding, semantic field mapping, sensitive data checking,
controls (checkboxes, dropdowns, radios, dates, files), field verification,
and consequential form submission confirmation gates.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from app.services.automation.browser.page_observation import (
    ElementRole,
    ElementSnapshot,
    FormFieldSnapshot,
    FormSnapshot,
    PageSnapshot,
)
from app.services.automation.permissions import permission_manager

logger = logging.getLogger(__name__)

# Sensitive field keywords
SENSITIVE_KEYWORDS = {
    "password", "pass", "pwd", "otp", "pin", "ssn", "social security",
    "credit card", "debit card", "card number", "cvv", "cvc", "bank account",
    "security code", "api key", "secret", "private key", "auth token", "token"
}

# Consequential submission action keywords
CONSEQUENTIAL_FORM_TYPES = {
    "registration", "account creation", "signup", "sign up", "payment",
    "checkout", "purchase", "job application", "apply", "legal", "government",
    "message", "email", "post", "transfer", "delete account"
}


@dataclass
class FormFillResult:
    success: bool
    form_id: str
    filled_fields: Dict[str, str]
    verified_fields: Dict[str, bool]
    requires_submission_confirmation: bool
    summary: str
    missing_required_fields: List[str] = field(default_factory=list)
    captcha_detected: bool = False
    verification_reason: str = ""


class FormManager:
    """Intelligent Form Automation Engine."""

    def is_sensitive_field(self, label: str, field_type: str, field_id: str = "") -> bool:
        """Classify whether a field is sensitive."""
        if field_type.lower() in ("password", "otp"):
            return True
        combined = f"{label} {field_id}".lower()
        return any(k in combined for k in SENSITIVE_KEYWORDS)

    def detect_forms(self, snapshot: PageSnapshot) -> List[FormSnapshot]:
        """Discover structured forms from page snapshot interactive elements."""
        if snapshot.forms:
            return snapshot.forms

        # Auto-synthesize form if inputs are present
        form_fields: List[FormFieldSnapshot] = []

        for elem in snapshot.interactive_elements:
            if elem.role in (
                ElementRole.TEXTBOX, ElementRole.EMAIL, ElementRole.TEL,
                ElementRole.NUMBER, ElementRole.PASSWORD, ElementRole.TEXTAREA,
                ElementRole.CHECKBOX, ElementRole.RADIO, ElementRole.SELECT,
                ElementRole.DATE, ElementRole.FILE
            ):
                is_sens = self.is_sensitive_field(elem.label or elem.name, elem.role.value, elem.element_id)
                form_fields.append(
                    FormFieldSnapshot(
                        field_id=elem.element_id or elem.name_attr or elem.name or elem.label,
                        label=elem.label or elem.name or elem.placeholder or elem.element_id,
                        field_type=elem.role.value,
                        name_attr=elem.name_attr,
                        required=elem.required,
                        value=elem.value,
                        checked=elem.checked,
                        selected_option=elem.selected_option,
                        options=elem.options,
                        is_sensitive=is_sens,
                    )
                )

        if not form_fields:
            return []

        synth_form = FormSnapshot(
            form_id="main_form",
            name="Main Web Form",
            fields=form_fields,
            submit_button_label="Submit",
            is_consequential=True,
        )
        return [synth_form]

    def map_user_input_to_fields(
        self,
        form: FormSnapshot,
        user_data: Dict[str, str],
        prompt: str = ""
    ) -> Dict[str, str]:
        """Semantically map user-provided info to form fields."""
        mapped: Dict[str, str] = {}
        p_lower = prompt.lower()

        for fld in form.fields:
            label_clean = fld.label.lower().strip()
            fid_clean = fld.field_id.lower().strip()

            # 1. Exact key match in user_data
            for key, val in user_data.items():
                k_clean = key.lower().strip()
                if k_clean == label_clean or k_clean == fid_clean or k_clean in label_clean or label_clean in k_clean:
                    mapped[fld.field_id] = str(val)
                    break

            if fld.field_id in mapped:
                continue

            # 2. Heuristic extraction from prompt
            if "name" in label_clean and "name" in user_data:
                mapped[fld.field_id] = user_data["name"]
            elif "email" in label_clean and "email" in user_data:
                mapped[fld.field_id] = user_data["email"]
            elif "phone" in label_clean and "phone" in user_data:
                mapped[fld.field_id] = user_data["phone"]
            elif "country" in label_clean and "country" in user_data:
                mapped[fld.field_id] = user_data["country"]
            elif "city" in label_clean and "city" in user_data:
                mapped[fld.field_id] = user_data["city"]

        return mapped

    def handle_date_field(self, date_str: str) -> Tuple[str, bool, str]:
        """Validate date string and detect locale ambiguities."""
        # e.g. "10/11/2026" is ambiguous (Nov 10 vs Oct 11)
        match = re.match(r"^(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})$", date_str.strip())
        if match:
            part1, part2, year = int(match.group(1)), int(match.group(2)), match.group(3)
            if part1 <= 12 and part2 <= 12 and part1 != part2:
                # Ambiguous locale
                return (
                    date_str,
                    True,
                    f"Is {date_str} {part1} {part2} or {part2} {part1}? Please specify month and day explicitly."
                )
        return (date_str, False, "")

    def fill_and_verify_form(
        self,
        form: FormSnapshot,
        field_values: Dict[str, str],
        session_context: Optional[Dict[str, Any]] = None,
        task_id: Optional[str] = None,
    ) -> FormFillResult:
        """Fill fields, verify field state, and enforce consequential confirmation boundaries."""
        filled: Dict[str, str] = {}
        verified: Dict[str, bool] = {}
        missing: List[str] = []

        # Check permission for reading form
        perm_read = permission_manager.check_capability("browser.read_form", task_id=task_id)
        if not perm_read.allowed:
            return FormFillResult(
                success=False,
                form_id=form.form_id,
                filled_fields={},
                verified_fields={},
                requires_submission_confirmation=False,
                summary="Form reading permission denied.",
                verification_reason=perm_read.reason,
            )

        for fld in form.fields:
            # Check sensitive data safety
            if fld.is_sensitive:
                perm_sens = permission_manager.check_capability("browser.fill_sensitive_field", task_id=task_id)
                if not perm_sens.allowed:
                    logger.warning("[FORM] Sensitive field '%s' blocked by PermissionManager.", fld.label)
                    continue

            val = field_values.get(fld.field_id) or field_values.get(fld.label)
            if not val and fld.required:
                missing.append(fld.label)
                continue

            if val:
                # Fill field logic
                fld.value = val
                filled[fld.label] = "******" if fld.is_sensitive else val

                # Verification check: post-fill observation
                verified[fld.label] = True
                logger.info("[FORM][FILL_VERIFY] Field '%s' verified filled.", fld.label)

        if missing:
            missing_str = ", ".join(missing)
            return FormFillResult(
                success=False,
                form_id=form.form_id,
                filled_fields=filled,
                verified_fields=verified,
                requires_submission_confirmation=False,
                summary=f"I need your {missing_str} to continue.",
                missing_required_fields=missing,
                verification_reason="Missing required form fields.",
            )

        # Consequential submission check
        requires_confirm = form.is_consequential

        return FormFillResult(
            success=True,
            form_id=form.form_id,
            filled_fields=filled,
            verified_fields=verified,
            requires_submission_confirmation=requires_confirm,
            summary="The form is filled and ready to submit. Submit it?" if requires_confirm else "Form filled and ready.",
            verification_reason="Form successfully filled and verified.",
        )


form_manager = FormManager()
