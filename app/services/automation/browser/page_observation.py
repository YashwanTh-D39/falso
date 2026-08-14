"""
Structured Page Observation & Form Representation Model for FALSO (FALSO 4.6 & 4.7).

Represents DOM/UI state, accessibility attributes, interactive elements, forms, and CAPTCHA detection.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class ElementRole(str, Enum):
    BUTTON = "button"
    TEXTBOX = "textbox"
    PASSWORD = "password"
    EMAIL = "email"
    TEL = "tel"
    NUMBER = "number"
    CHECKBOX = "checkbox"
    RADIO = "radio"
    SELECT = "select"
    TEXTAREA = "textarea"
    DATE = "date"
    FILE = "file"
    LINK = "link"
    FORM = "form"
    UNKNOWN = "unknown"


@dataclass
class ElementSnapshot:
    role: ElementRole
    name: str = ""
    label: str = ""
    placeholder: str = ""
    type_attr: str = ""
    element_id: str = ""
    name_attr: str = ""
    value: str = ""
    required: bool = False
    checked: bool = False
    selected_option: str = ""
    options: List[str] = field(default_factory=list)
    is_sensitive: bool = False
    is_interactive: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "role": self.role.value,
            "name": self.name or self.label or self.placeholder or self.element_id,
            "label": self.label,
            "placeholder": self.placeholder,
            "type": self.type_attr,
            "required": self.required,
            "value": "******" if self.is_sensitive and self.value else self.value,
            "checked": self.checked,
            "selected_option": self.selected_option,
            "options": self.options,
            "sensitive": self.is_sensitive,
        }


@dataclass
class FormFieldSnapshot:
    field_id: str
    label: str
    field_type: str  # text, email, tel, number, password, textarea, checkbox, radio, select, date, file
    name_attr: str = ""
    required: bool = False
    value: str = ""
    checked: bool = False
    selected_option: str = ""
    options: List[str] = field(default_factory=list)
    is_sensitive: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "field_id": self.field_id,
            "label": self.label,
            "type": self.field_type,
            "required": self.required,
            "value": "******" if self.is_sensitive and self.value else self.value,
            "checked": self.checked,
            "selected_option": self.selected_option,
            "options": self.options,
        }


@dataclass
class FormSnapshot:
    form_id: str = "main_form"
    name: str = "Form"
    fields: List[FormFieldSnapshot] = field(default_factory=list)
    submit_button_label: str = "Submit"
    is_consequential: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "form_id": self.form_id,
            "name": self.name,
            "fields": [f.to_dict() for f in self.fields],
            "submit_button": self.submit_button_label,
            "is_consequential": self.is_consequential,
        }


@dataclass
class PageSnapshot:
    url: str = "about:blank"
    title: str = ""
    visible_text: str = ""
    interactive_elements: List[ElementSnapshot] = field(default_factory=list)
    links: List[Dict[str, str]] = field(default_factory=list)
    buttons: List[Dict[str, str]] = field(default_factory=list)
    forms: List[FormSnapshot] = field(default_factory=list)
    has_captcha: bool = False
    ready_state: str = "complete"
    timestamp: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "url": self.url,
            "title": self.title,
            "has_captcha": self.has_captcha,
            "interactive_elements_count": len(self.interactive_elements),
            "links_count": len(self.links),
            "forms_count": len(self.forms),
            "forms": [f.to_dict() for f in self.forms],
        }


class PageObserver:
    """Observer component capturing structured page snapshots."""

    def observe_page(
        self,
        url: str = "https://www.google.com",
        title: str = "Google",
        visible_text: str = "",
        elements: Optional[List[ElementSnapshot]] = None,
        forms: Optional[List[FormSnapshot]] = None,
        has_captcha: bool = False,
    ) -> PageSnapshot:
        """Construct a structured PageSnapshot without polluting LLM context."""
        elem_list = elements or []
        form_list = forms or []

        # Auto-detect captcha from text/URL if not explicitly specified
        text_lower = (visible_text + " " + title + " " + url).lower()
        detected_captcha = has_captcha or any(
            k in text_lower for k in ("recaptcha", "hcaptcha", "cf-turnstile", "captcha", "are you a human", "bot detection")
        )

        return PageSnapshot(
            url=url,
            title=title,
            visible_text=visible_text[:1000],  # Bounded visible text
            interactive_elements=elem_list,
            links=[{"text": e.name or e.label, "url": e.value} for e in elem_list if e.role == ElementRole.LINK],
            buttons=[{"label": e.name or e.label} for e in elem_list if e.role == ElementRole.BUTTON],
            forms=form_list,
            has_captcha=detected_captcha,
        )


page_observer = PageObserver()
