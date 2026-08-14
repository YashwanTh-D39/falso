"""
FALSO 4.9 Adaptive Computer Observer.

Hierarchically queries the strongest available observation sources:
1. UI Automation (COM IUIAutomation)
2. Browser state & DOM
3. Window Manager (EnumWindows, GetForegroundWindow)
4. Screen observer
5. Process Manager (supporting information only)

Provides bounded, state-based wait primitives with strict timeouts.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from app.services.automation.operator.computer_state import (
    BrowserStateInfo,
    ComputerState,
    EvidenceType,
    StateValue,
    UIElementInfo,
    WindowInfo,
)
from app.services.automation.windows.process_manager import process_manager
from app.services.automation.windows.ui_automation import ui_automation
from app.services.automation.windows.window_manager import window_manager

logger = logging.getLogger(__name__)


class ComputerObserver:
    """Observes real Windows desktop state using hierarchical evidence channels."""

    def __init__(self) -> None:
        self._last_state: ComputerState | None = None

    def observe(self, target_hint: str | None = None) -> ComputerState:
        """Capture comprehensive computer state from strongest available sources."""
        now = time.time()
        state = ComputerState(timestamp=now)

        # 1. Window Manager: Foreground window & open visible windows (OBSERVED)
        fg_dict = window_manager.get_active_window()
        fg_hwnd = fg_dict.get("hwnd", 0)
        fg_title = fg_dict.get("title", "")
        fg_pid = fg_dict.get("process_id", 0)

        if fg_hwnd and fg_title:
            proc_name = ""
            if fg_pid:
                try:
                    import psutil
                    proc_name = psutil.Process(fg_pid).name()
                except Exception:
                    proc_name = ""
            w_info = WindowInfo(
                hwnd=fg_hwnd,
                title=fg_title,
                process_id=fg_pid,
                process_name=proc_name,
                is_foreground=True,
            )
            state.foreground_window = StateValue(
                value=w_info,
                evidence=EvidenceType.OBSERVED,
                source="window_manager.get_active_window",
            )
            # Identify foreground application name
            app_name = self._identify_app_name(fg_title, proc_name)
            state.foreground_application = StateValue(
                value=app_name,
                evidence=EvidenceType.OBSERVED,
                source="window_manager",
            )

        # Visible windows list (OBSERVED)
        open_wins = window_manager.list_windows()
        visible_list: list[WindowInfo] = []
        for w in open_wins:
            visible_list.append(
                WindowInfo(
                    hwnd=w.get("hwnd", 0),
                    title=w.get("title", ""),
                    process_id=w.get("process_id", 0),
                    process_name=w.get("process_name", ""),
                    is_foreground=(w.get("hwnd") == fg_hwnd),
                )
            )
        state.visible_windows = StateValue(
            value=visible_list,
            evidence=EvidenceType.OBSERVED,
            source="window_manager.list_windows",
        )

        # 2. Approved running applications (OBSERVED via process_manager / window_manager)
        running_apps: list[str] = []
        for known in ("Calculator", "Notepad", "Chrome", "Explorer", "Code"):
            if window_manager.is_window_open(known):
                running_apps.append(known)
        state.approved_running_applications = StateValue(
            value=running_apps,
            evidence=EvidenceType.OBSERVED,
            source="window_manager.is_window_open",
        )

        # 3. UI Automation: Focused element & visible UI elements (OBSERVED if UIA available)
        if ui_automation.is_available():
            try:
                elements = ui_automation.discover_elements(window_title=target_hint or fg_title)
                ui_elements = [
                    UIElementInfo(
                        name=el.get("name", ""),
                        role=el.get("role", ""),
                        control_type=el.get("control_type", ""),
                        automation_id=el.get("automation_id", ""),
                        value=el.get("value"),
                        enabled=el.get("enabled", True),
                        visible=el.get("visible", True),
                        bounding_rect=el.get("bounding_rect", (0, 0, 0, 0)),
                    )
                    for el in elements
                ]
                state.visible_elements = StateValue(
                    value=ui_elements,
                    evidence=EvidenceType.OBSERVED,
                    source="ui_automation.discover_elements",
                )
            except Exception as e:
                logger.debug("[OBSERVER] UIA element discovery failed: %s", e)

        # 4. Browser State (OBSERVED if browser active)
        if state.is_app_foreground("Chrome") or (target_hint and "chrome" in target_hint.lower()):
            b_info = self._observe_browser_state(fg_title)
            state.browser = StateValue(
                value=b_info,
                evidence=EvidenceType.OBSERVED if b_info else EvidenceType.UNKNOWN,
                source="browser_observation",
            )

        # Preserve verified action history from previous state
        if self._last_state and self._last_state.verified_action_history:
            state.verified_action_history = list(self._last_state.verified_action_history)
            state.last_verified_action = self._last_state.last_verified_action

        self._last_state = state
        return state

    def _identify_app_name(self, title: str, proc_name: str) -> str:
        t_low = title.lower()
        p_low = proc_name.lower()
        if "calculator" in t_low or "calculator" in p_low:
            return "Calculator"
        if "notepad" in t_low or "notepad" in p_low:
            return "Notepad"
        if "chrome" in t_low or "chrome" in p_low:
            return "Chrome"
        if "visual studio code" in t_low or "code" in p_low:
            return "VS Code"
        if "explorer" in t_low or "explorer" in p_low or "file explorer" in t_low:
            return "Explorer"
        return title.split(" - ")[-1] if " - " in title else title

    def _observe_browser_state(self, window_title: str) -> BrowserStateInfo:
        current_url = ""
        # Try extracting URL via UIA address bar
        if ui_automation.is_available():
            addr = ui_automation.get_element_value(name="Address and search bar") or ui_automation.get_element_value(automation_id="AddressBar")
            if addr:
                current_url = addr

        tab_title = window_title.replace(" - Google Chrome", "").strip() if "Google Chrome" in window_title else window_title
        return BrowserStateInfo(
            active_browser="Chrome",
            current_url=current_url,
            active_tab_title=tab_title,
            tab_count=1,
            known_tabs=[tab_title] if tab_title else [],
        )

    # ── Bounded State-Based Wait Functions ──

    def wait_for_window(self, title: str, timeout: float = 3.0, poll_interval: float = 0.2) -> bool:
        """Poll until window exists or timeout expires."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            if window_manager.is_window_open(title):
                return True
            time.sleep(poll_interval)
        return False

    def wait_for_foreground(self, target: str, timeout: float = 2.0, poll_interval: float = 0.1) -> bool:
        """Poll until target window is the active foreground window."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            if window_manager.verify_foreground(target):
                return True
            time.sleep(poll_interval)
        return False

    def wait_for_element(
        self,
        name: str | None = None,
        role: str | None = None,
        automation_id: str | None = None,
        window_title: str | None = None,
        timeout: float = 3.0,
        poll_interval: float = 0.2,
    ) -> UIElementInfo | None:
        """Poll until UI element is found in accessibility tree."""
        if not ui_automation.is_available():
            return None
        deadline = time.time() + timeout
        while time.time() < deadline:
            el = ui_automation.find_element(
                name=name,
                role=role,
                automation_id=automation_id,
                window_title=window_title,
            )
            if el:
                return UIElementInfo(
                    name=el.get("name", ""),
                    role=el.get("role", ""),
                    control_type=el.get("control_type", ""),
                    automation_id=el.get("automation_id", ""),
                    value=el.get("value"),
                    enabled=el.get("enabled", True),
                    visible=el.get("visible", True),
                    bounding_rect=el.get("bounding_rect", (0, 0, 0, 0)),
                )
            time.sleep(poll_interval)
        return None

    def wait_for_text(
        self,
        text: str,
        target: str | None = None,
        timeout: float = 3.0,
        poll_interval: float = 0.2,
    ) -> bool:
        """Poll until text is present in the target application's document/display."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            if ui_automation.is_available():
                val = ui_automation.get_element_value(window_title=target) or ui_automation.get_element_text(window_title=target)
                if val and text in val:
                    return True
            time.sleep(poll_interval)
        return False

    def wait_for_url(self, url: str, timeout: float = 4.0, poll_interval: float = 0.2) -> bool:
        """Poll until active browser URL or title reflects target URL."""
        deadline = time.time() + timeout
        url_clean = url.lower().replace("https://", "").replace("http://", "").replace("www.", "").strip("/")
        while time.time() < deadline:
            active = window_manager.get_active_window()
            title = active.get("title", "").lower()
            if url_clean in title:
                return True
            if ui_automation.is_available():
                addr = ui_automation.get_element_value(name="Address and search bar") or ""
                if url_clean in addr.lower():
                    return True
            time.sleep(poll_interval)
        return False

    def wait_for_ui_change(self, before_state: ComputerState, timeout: float = 3.0, poll_interval: float = 0.2) -> bool:
        """Poll until observable UI state changes from before_state."""
        deadline = time.time() + timeout
        before_fg = before_state.foreground_window.value.title if before_state.foreground_window.value else ""
        while time.time() < deadline:
            current = self.observe()
            current_fg = current.foreground_window.value.title if current.foreground_window.value else ""
            if current_fg != before_fg:
                return True
            time.sleep(poll_interval)
        return False

    def wait_for_browser_state(self, timeout: float = 3.0) -> BrowserStateInfo | None:
        """Poll until a valid browser state is observed."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            state = self.observe("Chrome")
            if state.browser.is_observed() and state.browser.value:
                return state.browser.value
            time.sleep(0.2)
        return None


computer_observer = ComputerObserver()
