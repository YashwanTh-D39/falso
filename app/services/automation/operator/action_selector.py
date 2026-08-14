"""
FALSO 4.9 Adaptive Action Selector.

Selects the safest, most reliable interaction mechanism based on:
goal, computer state, available capabilities, and permission level.

Preference hierarchy:
1. UI Automation (semantic accessibility tree)
2. Browser Automation (DOM-level interaction)
3. Application Skill (structured domain handlers)
4. Keyboard / Mouse Input (with strict foreground verification guard)
5. Honest Failure / Confirmation (never guess coordinates)
"""

from __future__ import annotations

from dataclasses import dataclass, field
import enum
import logging
import re
from typing import Any

from app.services.automation.operator.computer_state import ComputerState
from app.services.automation.permissions import PermissionLevel, RiskLevel, permission_manager
from app.services.automation.windows.ui_automation import ui_automation

logger = logging.getLogger(__name__)


class ControlMethod(enum.Enum):
    UI_AUTOMATION = "UI_AUTOMATION"
    BROWSER_AUTOMATION = "BROWSER_AUTOMATION"
    APPLICATION_SKILL = "APPLICATION_SKILL"
    ANDROID_SKILL = "ANDROID_SKILL"
    KEYBOARD_INPUT = "KEYBOARD_INPUT"
    MOUSE_INPUT = "MOUSE_INPUT"
    WINDOW_MANAGER = "WINDOW_MANAGER"
    USER_CONFIRMATION = "USER_CONFIRMATION"
    UNAVAILABLE = "UNAVAILABLE"


@dataclass
class ActionSelectionResult:
    method: ControlMethod
    target_app: str
    target_element: str | None = None
    action_name: str = ""
    params: dict[str, Any] = field(default_factory=dict)
    risk_level: RiskLevel = RiskLevel.LOW
    confidence: float = 1.0
    reasoning: str = ""
    requires_confirmation: bool = False


class ActionSelector:
    """Intelligently routes automation intent to the most reliable control method."""

    def select_action(
        self,
        goal: str,
        state: ComputerState,
        available_capabilities: list[str] | None = None,
    ) -> ActionSelectionResult:
        goal_clean = goal.lower().strip()

        # Check for Android / Phone Actions FIRST
        phone_unlock_phrases = (
            "unlock my device", "unlock my phone", "unlock my mobile", "unlock the phone",
            "unlock the device", "wake and unlock", "open my phone", "continue on my phone",
            "wake my phone", "wake the phone", "wake my device", "unlock phone", "unlock device",
            "wake phone", "wake device"
        )
        is_phone_unlock = any(p in goal_clean for p in phone_unlock_phrases)

        # Contextual "unlock it" / "wake it" via last verified target or pronoun context
        if goal_clean in ("unlock it", "wake it", "wake up it", "unlock this"):
            last_target = state.get_last_verified_target() if state else None
            if last_target in ("phone", "android", "device", "mobile", "android_device", "android_app"):
                is_phone_unlock = True

        phone_phrases = (
            "on my phone", "on phone", "on android", "on mobile", "on device", "on my device",
            "in my phone", "in phone", "in android", "in mobile", "in device", "in my device",
            "my phone", "phone battery", "phone storage", "screenshot on phone", "screenshot on my phone",
            "audit my phone", "phone security", "my device", "the phone", "the device", "my mobile"
        )
        is_phone_targeted = is_phone_unlock or any(w in goal_clean for w in phone_phrases) or goal_clean.startswith(("call ", "dial ", "message ", "sms ", "text "))

        if is_phone_targeted:
            # 1. Calling
            if goal_clean.startswith(("call ", "dial ")):
                target_name = goal_clean.replace("call ", "").replace("dial ", "").replace("on my phone", "").replace("on phone", "").strip()
                return ActionSelectionResult(
                    method=ControlMethod.ANDROID_SKILL,
                    target_app="android_call",
                    action_name="call",
                    params={"target": target_name},
                    risk_level=RiskLevel.HIGH,
                    reasoning=f"Initiate phone call to '{target_name}'.",
                )

            # 2. Messaging
            if goal_clean.startswith(("message ", "sms ", "text ")):
                m_parts = re.match(r"(?:message|sms|text)\s+([a-zA-Z0-9_\+]+)\s+(?:that\s+)?(.+)", goal_clean)
                recipient = m_parts.group(1) if m_parts else "recipient"
                msg = m_parts.group(2) if m_parts else goal
                return ActionSelectionResult(
                    method=ControlMethod.ANDROID_SKILL,
                    target_app="android_message",
                    action_name="message",
                    params={"recipient": recipient, "message": msg},
                    risk_level=RiskLevel.HIGH,
                    reasoning=f"Compose and confirm message to '{recipient}'.",
                )

            # 3. Unlock / Wake
            if is_phone_unlock:
                return ActionSelectionResult(
                    method=ControlMethod.ANDROID_SKILL,
                    target_app="android_device",
                    action_name="unlock_phone",
                    params={"goal": goal},
                    risk_level=RiskLevel.LOW,
                    reasoning="Initiate authorized unlock workflow for phone.",
                )

            # 4. Battery / Storage / Screenshot / Lock / Audit
            if "battery" in goal_clean:
                return ActionSelectionResult(
                    method=ControlMethod.ANDROID_SKILL,
                    target_app="android_device",
                    action_name="battery",
                    params={},
                    risk_level=RiskLevel.LOW,
                    reasoning="Check phone battery status.",
                )
            if "storage" in goal_clean:
                return ActionSelectionResult(
                    method=ControlMethod.ANDROID_SKILL,
                    target_app="android_device",
                    action_name="storage",
                    params={},
                    risk_level=RiskLevel.LOW,
                    reasoning="Check phone storage statistics.",
                )
            if "screenshot" in goal_clean:
                return ActionSelectionResult(
                    method=ControlMethod.ANDROID_SKILL,
                    target_app="android_device",
                    action_name="screenshot",
                    params={},
                    risk_level=RiskLevel.LOW,
                    reasoning="Capture screenshot on phone.",
                )
            if any(w in goal_clean for w in ("audit", "security")):
                return ActionSelectionResult(
                    method=ControlMethod.ANDROID_SKILL,
                    target_app="android_device",
                    action_name="audit_phone",
                    params={},
                    risk_level=RiskLevel.LOW,
                    reasoning="Perform security audit on phone.",
                )

            # 5. App Launching on Phone
            if any(goal_clean.startswith(v) for v in ("open ", "launch ", "start ", "run ")):
                app_name = self._extract_android_app_name(goal_clean)
                return ActionSelectionResult(
                    method=ControlMethod.ANDROID_SKILL,
                    target_app="android_app",
                    action_name="launch_android_app",
                    params={"app": app_name},
                    risk_level=RiskLevel.LOW,
                    reasoning=f"Launch application '{app_name}' on phone.",
                )

            # Default device query
            return ActionSelectionResult(
                method=ControlMethod.ANDROID_SKILL,
                target_app="android_device",
                action_name="battery",
                params={},
                risk_level=RiskLevel.LOW,
                reasoning="Check phone battery status.",
            )

        # 1. Check for Window Lifecycle (open/close/focus)
        if goal_clean.startswith(("open ", "launch ", "start ")):
            app_target = self._extract_app_name(goal_clean)
            return ActionSelectionResult(
                method=ControlMethod.WINDOW_MANAGER,
                target_app=app_target,
                action_name="open_app",
                params={"app": app_target},
                risk_level=RiskLevel.LOW,
                reasoning=f"Open application {app_target} using WindowManager.",
            )

        if goal_clean.startswith(("close ", "exit ", "quit ")):
            app_target = self._extract_app_name(goal_clean)
            return ActionSelectionResult(
                method=ControlMethod.WINDOW_MANAGER,
                target_app=app_target,
                action_name="close_window",
                params={"app": app_target},
                risk_level=RiskLevel.LOW,
                reasoning=f"Close application {app_target} safely.",
            )

        if goal_clean.startswith(("focus ", "switch to ")):
            app_target = self._extract_app_name(goal_clean)
            return ActionSelectionResult(
                method=ControlMethod.WINDOW_MANAGER,
                target_app=app_target,
                action_name="focus_window",
                params={"app": app_target},
                risk_level=RiskLevel.LOW,
                reasoning=f"Bring {app_target} to foreground.",
            )

        # Check for Cybersecurity Diagnostic & Intelligence queries
        if any(w in goal_clean for w in (
            "port ", "listening", "reachable", "connect to localhost", "server logs",
            "network config", "resolve ", "dns", "unusual listening ports", "why can't my",
            "why cant my", "is port", "check port", "inspect logs", "what is running",
            "what's running", "what changed", "show changes", "is anything unusual",
            "is anything suspicious", "security check", "what happened before", "baseline"
        )) and not goal_clean.startswith(("open ", "launch ")):
            return ActionSelectionResult(
                method=ControlMethod.APPLICATION_SKILL,
                target_app="security",
                action_name="diagnose",
                params={"query": goal, "goal": goal},
                risk_level=RiskLevel.LOW,
                reasoning=f"Perform cybersecurity diagnostic investigation for '{goal}'.",
            )

        # 2. Check for Web / Browser actions
        if any(w in goal_clean for w in ("new tab", "close tab", "navigate", "search", "go to", "http", ".com", ".org", ".net")):
            target_app = "Chrome"
            if "new tab" in goal_clean:
                return ActionSelectionResult(
                    method=ControlMethod.APPLICATION_SKILL,
                    target_app=target_app,
                    action_name="new_tab",
                    params={"app": "Chrome"},
                    risk_level=RiskLevel.LOW,
                    reasoning="Open new tab in Chrome.",
                )
            if "close tab" in goal_clean:
                return ActionSelectionResult(
                    method=ControlMethod.APPLICATION_SKILL,
                    target_app=target_app,
                    action_name="close_tab",
                    params={"app": "Chrome"},
                    risk_level=RiskLevel.LOW,
                    reasoning="Close current Chrome tab.",
                )
            if any(w in goal_clean for w in ("go to ", "navigate ", "open http", "open https")):
                url = self._extract_url(goal_clean)
                return ActionSelectionResult(
                    method=ControlMethod.BROWSER_AUTOMATION,
                    target_app=target_app,
                    action_name="navigate",
                    params={"url": url},
                    risk_level=RiskLevel.LOW,
                    reasoning=f"Navigate to {url} in browser.",
                )

        # 3. Check for Calculator Actions
        if any(w in goal_clean for w in ("calculate", "plus", "minus", "times", "divided", "+", "-", "*", "/")) and any(c.isdigit() for c in goal_clean):
            return ActionSelectionResult(
                method=ControlMethod.APPLICATION_SKILL,
                target_app="Calculator",
                action_name="calculate",
                params={"goal": goal},
                risk_level=RiskLevel.LOW,
                reasoning="Calculate arithmetic expression in Calculator.",
            )

        # 4. Check for Notepad / Document Actions
        if "type " in goal_clean:
            text = goal.split("type ", 1)[-1].strip(" '\"")
            target = state.get_foreground_app() or "Notepad"
            return ActionSelectionResult(
                method=ControlMethod.APPLICATION_SKILL,
                target_app=target,
                action_name="type_text",
                params={"text": text},
                risk_level=RiskLevel.LOW,
                reasoning=f"Type text into {target}.",
            )

        if "copy" in goal_clean:
            target = state.get_foreground_app() or "Notepad"
            return ActionSelectionResult(
                method=ControlMethod.APPLICATION_SKILL,
                target_app=target,
                action_name="copy",
                params={},
                risk_level=RiskLevel.LOW,
                reasoning=f"Copy content in {target}.",
            )

        if "paste" in goal_clean:
            target = state.get_foreground_app() or "Notepad"
            return ActionSelectionResult(
                method=ControlMethod.APPLICATION_SKILL,
                target_app=target,
                action_name="paste",
                params={},
                risk_level=RiskLevel.LOW,
                reasoning=f"Paste clipboard content into {target}.",
            )

        # 5. Check for UI Automation Semantic Target (Buttons, Controls)
        if goal_clean.startswith("click "):
            target_el = goal_clean.replace("click ", "").replace("button", "").replace("the ", "").strip(" '\"")
            if ui_automation.is_available():
                found = ui_automation.find_element(name=target_el)
                if found:
                    return ActionSelectionResult(
                        method=ControlMethod.UI_AUTOMATION,
                        target_app=state.get_foreground_app() or "",
                        target_element=target_el,
                        action_name="click_element",
                        params={"name": target_el},
                        risk_level=RiskLevel.LOW,
                        reasoning=f"Click '{target_el}' using UI Automation.",
                    )
            # If element cannot be verified via UIA, do NOT guess coordinates
            return ActionSelectionResult(
                method=ControlMethod.UNAVAILABLE,
                target_app=state.get_foreground_app() or "",
                target_element=target_el,
                action_name="click",
                risk_level=RiskLevel.LOW,
                confidence=0.0,
                reasoning=f"Cannot reliably locate element '{target_el}'. Refusing to guess screen coordinates.",
            )

        # Fallback to Application Skill / Window Manager
        return ActionSelectionResult(
            method=ControlMethod.APPLICATION_SKILL,
            target_app=state.get_foreground_app() or "system",
            action_name="general_action",
            params={"goal": goal},
            risk_level=RiskLevel.LOW,
            reasoning="Execute via structured skill handler.",
        )

    def _extract_app_name(self, text: str) -> str:
        t = text.lower()
        if "calculator" in t:
            return "Calculator"
        if "notepad" in t:
            return "Notepad"
        if "chrome" in t or "browser" in t:
            return "Chrome"
        if "code" in t or "vs code" in t or "vscode" in t:
            return "VS Code"
        if "explorer" in t or "files" in t:
            return "Explorer"
        words = text.split()
        return words[1].capitalize() if len(words) > 1 else "Unknown"

    def _extract_android_app_name(self, text: str) -> str:
        t = text.lower()
        for phrase in (
            "on my phone", "on phone", "on android", "on mobile", "on device", "on my device",
            "in my phone", "in phone", "in android", "in mobile", "in device", "in my device",
            "my phone", "the phone", "my device", "the device", "my mobile", "the mobile"
        ):
            t = t.replace(phrase, "")
        t = re.sub(r"^(?:open|launch|start|run)\s+", "", t.strip())
        return t.strip(" .,!?;:")

    def _extract_url(self, text: str) -> str:
        for word in text.split():
            if word.startswith(("http://", "https://")):
                return word
            if ".com" in word or ".org" in word or ".net" in word or ".io" in word:
                return f"https://{word.strip('.,')}"
        if "github" in text:
            return "https://github.com"
        return "https://google.com"


action_selector = ActionSelector()
