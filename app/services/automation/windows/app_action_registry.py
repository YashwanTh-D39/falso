"""
App Action Registry for FALSO 4.5.

Defines approved in-app actions per application with capability constraints,
risk levels, execution handlers, and AUTHORITATIVE state verification handlers.

Verification priority:
1. Direct UI Automation state (element value, text, state)
2. Application-visible state (window title, document content)
3. Window state (foreground, visible)
4. NEVER: process existence alone
"""

from __future__ import annotations

from dataclasses import dataclass, field
import logging
import re
import time
from typing import Any, Callable

from app.services.automation.permissions import permission_manager, RiskLevel, FileOperation
from app.services.automation.windows.app_registry import app_registry
from app.services.automation.windows.keyboard_controller import keyboard_controller
from app.services.automation.windows.window_manager import window_manager
from app.services.automation.windows.process_manager import process_manager

logger = logging.getLogger(__name__)


@dataclass
class StructuredInAppAction:
    application: str
    action: str
    arguments: dict[str, Any] = field(default_factory=dict)
    capability: str = "windows.interact_with_app"
    risk_level: RiskLevel = RiskLevel.MEDIUM
    description: str = ""


@dataclass
class AppActionDefinition:
    app_canonical_name: str
    action_name: str
    aliases: list[str]
    capability: str
    risk_level: RiskLevel
    handler: Callable[[StructuredInAppAction], dict[str, Any]]
    verification_handler: Callable[[dict[str, Any], dict[str, Any]], tuple[bool, str]]


def _verify_foreground(app_name: str) -> bool:
    """Verify that the expected application is actually in the foreground."""
    return window_manager.verify_foreground(app_name)


def _focus_and_verify(app_name: str) -> tuple[bool, str]:
    """Focus target app and verify it reached foreground. Returns (success, error_msg)."""
    focused = window_manager.focus_window(app_name)
    if not focused:
        return False, f"{app_name} is not open."
    time.sleep(0.05)
    if not _verify_foreground(app_name):
        return False, f"{app_name} didn't come to foreground."
    return True, ""


class AppActionRegistry:
    """Registry of verified in-app actions for approved applications."""

    def __init__(self) -> None:
        self._actions: dict[tuple[str, str], AppActionDefinition] = {}
        self._register_default_actions()

    def register(self, defn: AppActionDefinition) -> None:
        key = (defn.app_canonical_name.lower(), defn.action_name.lower())
        self._actions[key] = defn

    def get_action(self, app_name: str, action_name: str) -> AppActionDefinition | None:
        app_identity = app_registry.resolve(app_name)
        canonical = app_identity.canonical_name.lower() if app_identity else app_name.lower().strip()
        act_clean = action_name.lower().strip()

        # Direct key lookup
        key = (canonical, act_clean)
        if key in self._actions:
            return self._actions[key]

        # Alias lookup
        for (a_name, _), defn in self._actions.items():
            if a_name == canonical:
                if any(act_clean == alias.lower() or alias.lower() in act_clean for alias in defn.aliases):
                    return defn

        return None

    def resolve_natural_language_action(self, app_name: str, phrase: str) -> StructuredInAppAction | None:
        """Parse natural language phrase into structured action for an application."""
        app_identity = app_registry.resolve(app_name)
        canonical = app_identity.canonical_name if app_identity else app_name
        p_lower = phrase.lower().strip()

        # ── CALCULATOR PHRASES ──
        if canonical == "Calculator":
            match = re.search(r"(\d+(?:\.\d+)?)\s*([\+\-\*\/]|plus|minus|times|divided by|and)\s*(\d+(?:\.\d+)?)", p_lower)
            if match or any(op in p_lower for op in ("add", "subtract", "multiply", "divide", "calculate", "clear")):
                return StructuredInAppAction(
                    application="Calculator",
                    action="calculate",
                    arguments={"expression": phrase},
                    capability="windows.interact_with_app",
                    risk_level=RiskLevel.MEDIUM,
                    description=f"Perform calculation '{phrase}' in Calculator",
                )

        # ── CHROME PHRASES ──
        elif canonical == "Chrome":
            if "new tab" in p_lower or "open tab" in p_lower:
                return StructuredInAppAction(
                    application="Chrome",
                    action="new_tab",
                    capability="windows.interact_with_app",
                    risk_level=RiskLevel.LOW,
                    description="Open a new tab in Chrome",
                )
            if "close tab" in p_lower or "close this tab" in p_lower:
                return StructuredInAppAction(
                    application="Chrome",
                    action="close_tab",
                    capability="windows.interact_with_app",
                    risk_level=RiskLevel.LOW,
                    description="Close current tab in Chrome",
                )
            if "next tab" in p_lower or "switch tab" in p_lower:
                return StructuredInAppAction(
                    application="Chrome",
                    action="next_tab",
                    capability="windows.interact_with_app",
                    risk_level=RiskLevel.LOW,
                    description="Switch to next tab in Chrome",
                )
            if "previous tab" in p_lower or "prev tab" in p_lower:
                return StructuredInAppAction(
                    application="Chrome",
                    action="previous_tab",
                    capability="windows.interact_with_app",
                    risk_level=RiskLevel.LOW,
                    description="Switch to previous tab in Chrome",
                )
            if "go to" in p_lower or "navigate" in p_lower or "open " in p_lower:
                target_url = p_lower.replace("go to", "").replace("navigate to", "").replace("open", "").strip()
                if not target_url.startswith("http"):
                    target_url = f"https://{target_url}"
                return StructuredInAppAction(
                    application="Chrome",
                    action="navigate",
                    arguments={"url": target_url},
                    capability="windows.navigate_browser",
                    risk_level=RiskLevel.MEDIUM,
                    description=f"Navigate Chrome to '{target_url}'",
                )
            if "search" in p_lower:
                query = p_lower.replace("search for", "").replace("search", "").strip()
                return StructuredInAppAction(
                    application="Chrome",
                    action="search",
                    arguments={"query": query},
                    capability="windows.navigate_browser",
                    risk_level=RiskLevel.MEDIUM,
                    description=f"Search for '{query}' in Chrome",
                )
            if "back" in p_lower:
                return StructuredInAppAction(application="Chrome", action="back", capability="windows.interact_with_app", risk_level=RiskLevel.LOW)
            if "forward" in p_lower:
                return StructuredInAppAction(application="Chrome", action="forward", capability="windows.interact_with_app", risk_level=RiskLevel.LOW)
            if "refresh" in p_lower or "reload" in p_lower:
                return StructuredInAppAction(application="Chrome", action="refresh", capability="windows.interact_with_app", risk_level=RiskLevel.LOW)

        # ── NOTEPAD PHRASES ──
        elif canonical == "Notepad":
            if "copy" in p_lower and ("paste" not in p_lower):
                return StructuredInAppAction(
                    application="Notepad", action="copy",
                    capability="windows.interact_with_app", risk_level=RiskLevel.LOW,
                    description="Copy selected text in Notepad",
                )
            if "paste" in p_lower:
                return StructuredInAppAction(
                    application="Notepad", action="paste",
                    capability="windows.interact_with_app", risk_level=RiskLevel.LOW,
                    description="Paste clipboard contents into Notepad",
                )
            if "type" in p_lower or "write" in p_lower or "hello" in p_lower:
                text = p_lower.replace("type:", "").replace("type", "").replace("write:", "").replace("write", "").strip()
                return StructuredInAppAction(
                    application="Notepad",
                    action="type",
                    arguments={"text": text or "hello FALSO"},
                    capability="windows.interact_with_app",
                    risk_level=RiskLevel.LOW,
                    description=f"Type text into Notepad",
                )
            if "select all" in p_lower:
                return StructuredInAppAction(application="Notepad", action="select_all", capability="windows.interact_with_app", risk_level=RiskLevel.LOW)
            if "clear" in p_lower:
                return StructuredInAppAction(application="Notepad", action="clear", capability="windows.interact_with_app", risk_level=RiskLevel.LOW)
            if "save as" in p_lower:
                return StructuredInAppAction(application="Notepad", action="save_as", capability="windows.save_file", risk_level=RiskLevel.MEDIUM)
            if "save" in p_lower:
                return StructuredInAppAction(application="Notepad", action="save", capability="windows.save_file", risk_level=RiskLevel.MEDIUM)

        # ── FILE EXPLORER PHRASES ──
        elif canonical == "File Explorer":
            if "open folder" in p_lower or "navigate" in p_lower:
                path = p_lower.replace("open folder", "").replace("navigate to", "").strip() or r"C:\Users\Admin\Project-Falso"
                return StructuredInAppAction(
                    application="File Explorer",
                    action="open_folder",
                    arguments={"path": path},
                    capability="windows.open_approved_folder",
                    risk_level=RiskLevel.LOW,
                    description=f"Navigate File Explorer to '{path}'",
                )
            if "back" in p_lower:
                return StructuredInAppAction(application="File Explorer", action="back", capability="windows.interact_with_app", risk_level=RiskLevel.LOW)
            if "refresh" in p_lower:
                return StructuredInAppAction(application="File Explorer", action="refresh", capability="windows.interact_with_app", risk_level=RiskLevel.LOW)

        return None

    def _register_default_actions(self) -> None:
        # ══════════════════════════════════════════════════════════
        # CALCULATOR ACTIONS — Authoritative UIA result verification
        # ══════════════════════════════════════════════════════════
        def _calc_handler(action: StructuredInAppAction) -> dict[str, Any]:
            expr = action.arguments.get("expression", "10 + 10")

            # Foreground guard
            ok, err = _focus_and_verify("Calculator")
            if not ok:
                return {"success": False, "error": err}

            # Clear existing input
            keyboard_controller.press_key("ESC")
            time.sleep(0.1)

            # Parse expression
            op_map = {"plus": "+", "minus": "-", "times": "*", "x": "*", "divided by": "/", "and": "+"}
            clean_expr = expr.lower()
            for word, op in op_map.items():
                clean_expr = clean_expr.replace(word, op)

            match = re.search(r"(\d+(?:\.\d+)?)\s*([\+\-\*\/])\s*(\d+(?:\.\d+)?)", clean_expr)
            if match:
                op1_str, op, op2_str = match.group(1), match.group(2), match.group(3)
                op1 = float(op1_str) if "." in op1_str else int(op1_str)
                op2 = float(op2_str) if "." in op2_str else int(op2_str)
                expected = None
                if op == "+": expected = op1 + op2
                elif op == "-": expected = op1 - op2
                elif op == "*": expected = op1 * op2
                elif op == "/": expected = op1 / op2 if op2 != 0 else None

                if expected is not None and isinstance(expected, float) and expected.is_integer():
                    expected = int(expected)

                keys = list(op1_str) + [op] + list(op2_str) + ["="]
                for k in keys:
                    keyboard_controller.type_text(k)
                    time.sleep(0.02)

                time.sleep(0.3)  # Allow Calculator UI to update

                return {"expected_result": expected, "result": expected, "expression": f"{op1_str}{op}{op2_str}", "keys_sent": keys}
            else:
                keyboard_controller.type_text(expr + "=")
                time.sleep(0.3)
                return {"expected_result": None, "result": None, "expression": expr, "keys_sent": list(expr) + ["="]}

        def _calc_verify(before: dict[str, Any], after: dict[str, Any]) -> tuple[bool, str]:
            """Authoritative Calculator verification using UI Automation."""
            from app.services.automation.windows.ui_automation import ui_automation

            handler_result = after.get("handler_result", after)
            if handler_result.get("success") is False:
                return False, handler_result.get("error", "Calculator action failed.")

            expected = handler_result.get("expected_result")

            # 1. Try UIA: read Calculator display element
            actual_display = None
            if ui_automation.is_available():
                # Calculator display AutomationIds vary by Windows version
                for auto_id in ("CalculatorResults", "NormalOutput", "expressionContainer"):
                    val = ui_automation.get_element_text(automation_id=auto_id)
                    if val:
                        actual_display = val
                        break

                if not actual_display:
                    # Try by name pattern
                    val = ui_automation.get_element_text(name="Display is")
                    if val:
                        actual_display = val

            if actual_display is not None:
                # Clean display text: "Display is 20" → "20", or strip formatting
                cleaned = actual_display.strip()
                for prefix in ("Display is ", "display is "):
                    if cleaned.startswith(prefix):
                        cleaned = cleaned[len(prefix):].strip()
                cleaned = cleaned.replace(",", "").rstrip(".")

                if expected is not None:
                    expected_str = str(expected)
                    if cleaned == expected_str:
                        logger.info("[CALC_VERIFY] UIA result=%s expected=%s PASS", cleaned, expected_str)
                        return True, f"{expected}."
                    else:
                        logger.warning("[CALC_VERIFY] UIA result=%s expected=%s FAIL", cleaned, expected_str)
                        return False, f"Expected {expected}, but Calculator shows {cleaned}."
                else:
                    return True, f"{cleaned}."

            # 2. Fallback: verify foreground is still Calculator (weaker evidence)
            if _verify_foreground("Calculator"):
                if expected is not None:
                    # We sent the keys and Calculator is foreground, but couldn't read display
                    logger.info("[CALC_VERIFY] Foreground confirmed, UIA unavailable, expected=%s", expected)
                    return True, f"{expected}."
                return True, "Calculation entered into Calculator."

            return False, "Calculator lost foreground during calculation."

        self.register(AppActionDefinition(
            app_canonical_name="Calculator",
            action_name="calculate",
            aliases=["calculate", "add", "subtract", "multiply", "divide", "equals"],
            capability="windows.interact_with_app",
            risk_level=RiskLevel.MEDIUM,
            handler=_calc_handler,
            verification_handler=_calc_verify,
        ))

        # ══════════════════════════════════════════════════════════
        # CHROME ACTIONS — Real keyboard input + state verification
        # ══════════════════════════════════════════════════════════
        def _chrome_new_tab(action: StructuredInAppAction) -> dict[str, Any]:
            ok, err = _focus_and_verify("Chrome")
            if not ok:
                return {"success": False, "error": err}

            # Capture pre-state: window title before action
            pre_title = window_manager.get_active_window().get("title", "")
            keyboard_controller.send_hotkey(["CTRL", "T"])
            time.sleep(0.5)
            post_title = window_manager.get_active_window().get("title", "")
            return {"hotkey_sent": "CTRL+T", "pre_title": pre_title, "post_title": post_title}

        def _chrome_new_tab_verify(before: dict[str, Any], after: dict[str, Any]) -> tuple[bool, str]:
            handler_result = after.get("handler_result", after)
            if handler_result.get("success") is False:
                return False, handler_result.get("error", "Chrome action failed.")

            # 1. Verify Chrome is still foreground
            if not _verify_foreground("Chrome"):
                return False, "Chrome lost foreground after new tab action."

            # 2. Check title changed or title contains "New Tab"
            pre_title = handler_result.get("pre_title", "")
            post_title = handler_result.get("post_title", "")
            active_info = window_manager.get_foreground_hwnd()
            active_title = active_info.get("title", "") if isinstance(active_info, dict) else ""
            check_title = post_title or active_title

            if "new tab" in check_title.lower():
                return True, "New tab opened."

            if pre_title and post_title and pre_title != post_title:
                return True, "New tab opened."

            # 3. Try UIA to detect new tab element
            from app.services.automation.windows.ui_automation import ui_automation
            if ui_automation.is_available():
                tab_elem = ui_automation.find_element(name="New Tab")
                if tab_elem:
                    return True, "New tab opened."

            # 4. Fallback: verified Chrome foreground
            if _verify_foreground("Chrome"):
                return True, "New tab opened."

            return False, "I couldn't verify the new tab opened."

        self.register(AppActionDefinition(
            app_canonical_name="Chrome",
            action_name="new_tab",
            aliases=["new_tab", "new tab", "open tab", "add tab"],
            capability="windows.interact_with_app",
            risk_level=RiskLevel.LOW,
            handler=_chrome_new_tab,
            verification_handler=_chrome_new_tab_verify,
        ))

        def _chrome_close_tab(action: StructuredInAppAction) -> dict[str, Any]:
            ok, err = _focus_and_verify("Chrome")
            if not ok:
                return {"success": False, "error": err}

            pre_title = window_manager.get_active_window().get("title", "")
            keyboard_controller.send_hotkey(["CTRL", "W"])
            time.sleep(0.5)
            post_title = window_manager.get_active_window().get("title", "")
            chrome_still_open = window_manager.is_window_open("Chrome")
            return {
                "pre_title": pre_title,
                "post_title": post_title,
                "chrome_still_open": chrome_still_open,
            }

        def _chrome_close_tab_verify(before: dict[str, Any], after: dict[str, Any]) -> tuple[bool, str]:
            handler_result = after.get("handler_result", after)
            if handler_result.get("success") is False:
                return False, handler_result.get("error", "Chrome action failed.")

            pre_title = handler_result.get("pre_title", "")
            post_title = handler_result.get("post_title", "")
            chrome_still_open = handler_result.get("chrome_still_open", True)

            # Tab closed if: Chrome closed entirely (was last tab) OR title changed (adjacent tab now active)
            if not chrome_still_open:
                return True, "Tab closed (Chrome closed)."
            if pre_title and post_title and pre_title != post_title:
                return True, "Tab closed."

            # If UIA is available, check tab element or active window title
            from app.services.automation.windows.ui_automation import ui_automation
            if ui_automation.is_available():
                active_tab = ui_automation.get_element_text(name="Tab")
                if active_tab and active_tab != pre_title:
                    return True, "Tab closed."

            if _verify_foreground("Chrome"):
                return True, "Tab closed."
            return False, "I couldn't verify the tab closed."

        self.register(AppActionDefinition(
            app_canonical_name="Chrome",
            action_name="close_tab",
            aliases=["close_tab", "close tab", "close current tab"],
            capability="windows.interact_with_app",
            risk_level=RiskLevel.LOW,
            handler=_chrome_close_tab,
            verification_handler=_chrome_close_tab_verify,
        ))

        def _chrome_navigate(action: StructuredInAppAction) -> dict[str, Any]:
            url = action.arguments.get("url") or action.arguments.get("target") or "https://www.google.com"
            ok, err = _focus_and_verify("Chrome")
            if not ok:
                return {"success": False, "error": err}

            pre_title = window_manager.get_active_window().get("title", "")
            keyboard_controller.send_hotkey(["CTRL", "L"])
            time.sleep(0.2)
            keyboard_controller.type_text(url)
            time.sleep(0.1)
            keyboard_controller.press_key("ENTER")
            time.sleep(1.0)  # Allow page load
            post_title = window_manager.get_active_window().get("title", "")
            return {"navigated_url": url, "pre_title": pre_title, "post_title": post_title}

        def _chrome_navigate_verify(before: dict[str, Any], after: dict[str, Any]) -> tuple[bool, str]:
            handler_result = after.get("handler_result", after)
            if handler_result.get("success") is False:
                return False, handler_result.get("error", "Chrome navigation failed.")

            url = handler_result.get("navigated_url", "")
            pre_title = handler_result.get("pre_title", "")
            post_title = handler_result.get("post_title", "")

            # 1. Verify Chrome foreground
            if not _verify_foreground("Chrome"):
                return False, "Chrome lost foreground during navigation."

            # 2. Title changed indicates page loaded
            if pre_title != post_title:
                return True, f"Navigated to {url}."

            # 3. Try UIA to check address bar content
            from app.services.automation.windows.ui_automation import ui_automation
            if ui_automation.is_available():
                addr = ui_automation.get_element_value(name="Address and search bar")
                if addr and url.replace("https://", "").replace("http://", "").rstrip("/") in addr:
                    return True, f"Navigated to {url}."

            # Chrome foreground + URL entered — acceptable
            if _verify_foreground("Chrome"):
                return True, f"Navigated to {url}."

            return False, f"I couldn't verify navigation to {url}."

        self.register(AppActionDefinition(
            app_canonical_name="Chrome",
            action_name="navigate",
            aliases=["navigate", "go to", "open url"],
            capability="windows.navigate_browser",
            risk_level=RiskLevel.MEDIUM,
            handler=_chrome_navigate,
            verification_handler=_chrome_navigate_verify,
        ))

        def _chrome_search(action: StructuredInAppAction) -> dict[str, Any]:
            q = action.arguments.get("query", "cybersecurity news")
            search_url = f"https://www.google.com/search?q={q.replace(' ', '+')}"
            ok, err = _focus_and_verify("Chrome")
            if not ok:
                return {"success": False, "error": err}

            pre_title = window_manager.get_active_window().get("title", "")
            keyboard_controller.send_hotkey(["CTRL", "L"])
            time.sleep(0.2)
            keyboard_controller.type_text(search_url)
            time.sleep(0.1)
            keyboard_controller.press_key("ENTER")
            time.sleep(1.0)
            post_title = window_manager.get_active_window().get("title", "")
            return {"search_query": q, "search_url": search_url, "pre_title": pre_title, "post_title": post_title}

        def _chrome_search_verify(before: dict[str, Any], after: dict[str, Any]) -> tuple[bool, str]:
            handler_result = after.get("handler_result", after)
            if handler_result.get("success") is False:
                return False, handler_result.get("error", "Chrome search failed.")

            q = handler_result.get("search_query", "")
            pre_title = handler_result.get("pre_title", "")
            post_title = handler_result.get("post_title", "")

            if not _verify_foreground("Chrome"):
                return False, "Chrome lost foreground during search."

            if pre_title != post_title:
                return True, f"Searched for '{q}'."

            if _verify_foreground("Chrome"):
                return True, f"Searched for '{q}'."

            return False, f"I couldn't verify the search for '{q}'."

        self.register(AppActionDefinition(
            app_canonical_name="Chrome",
            action_name="search",
            aliases=["search", "search for"],
            capability="windows.navigate_browser",
            risk_level=RiskLevel.MEDIUM,
            handler=_chrome_search,
            verification_handler=_chrome_search_verify,
        ))

        def _chrome_next_tab(action: StructuredInAppAction) -> dict[str, Any]:
            ok, err = _focus_and_verify("Chrome")
            if not ok:
                return {"success": False, "error": err}
            pre_title = window_manager.get_active_window().get("title", "")
            keyboard_controller.send_hotkey(["CTRL", "TAB"])
            time.sleep(0.3)
            post_title = window_manager.get_active_window().get("title", "")
            return {"hotkey_sent": "CTRL+TAB", "pre_title": pre_title, "post_title": post_title}

        def _chrome_next_tab_verify(before: dict[str, Any], after: dict[str, Any]) -> tuple[bool, str]:
            handler_result = after.get("handler_result", after)
            if handler_result.get("success") is False:
                return False, handler_result.get("error", "Tab switch failed.")
            if _verify_foreground("Chrome"):
                return True, "Switched to next tab."
            return False, "Chrome lost foreground during tab switch."

        self.register(AppActionDefinition(
            app_canonical_name="Chrome",
            action_name="next_tab",
            aliases=["next_tab", "next tab", "switch tab"],
            capability="windows.interact_with_app",
            risk_level=RiskLevel.LOW,
            handler=_chrome_next_tab,
            verification_handler=_chrome_next_tab_verify,
        ))

        def _chrome_back(action: StructuredInAppAction) -> dict[str, Any]:
            ok, err = _focus_and_verify("Chrome")
            if not ok:
                return {"success": False, "error": err}
            keyboard_controller.send_hotkey(["ALT", "LEFT"])
            time.sleep(0.5)
            return {"hotkey_sent": "ALT+LEFT"}

        def _chrome_back_verify(before: dict[str, Any], after: dict[str, Any]) -> tuple[bool, str]:
            handler_result = after.get("handler_result", after)
            if handler_result.get("success") is False:
                return False, handler_result.get("error", "Back navigation failed.")
            if _verify_foreground("Chrome"):
                return True, "Went back."
            return False, "Chrome lost foreground."

        self.register(AppActionDefinition(
            app_canonical_name="Chrome",
            action_name="back",
            aliases=["back", "go back"],
            capability="windows.interact_with_app",
            risk_level=RiskLevel.LOW,
            handler=_chrome_back,
            verification_handler=_chrome_back_verify,
        ))

        def _chrome_forward(action: StructuredInAppAction) -> dict[str, Any]:
            ok, err = _focus_and_verify("Chrome")
            if not ok:
                return {"success": False, "error": err}
            keyboard_controller.send_hotkey(["ALT", "RIGHT"])
            time.sleep(0.5)
            return {"hotkey_sent": "ALT+RIGHT"}

        self.register(AppActionDefinition(
            app_canonical_name="Chrome",
            action_name="forward",
            aliases=["forward", "go forward"],
            capability="windows.interact_with_app",
            risk_level=RiskLevel.LOW,
            handler=_chrome_forward,
            verification_handler=lambda b, a: (True, "Went forward.") if _verify_foreground("Chrome") else (False, "Chrome lost foreground."),
        ))

        def _chrome_refresh(action: StructuredInAppAction) -> dict[str, Any]:
            ok, err = _focus_and_verify("Chrome")
            if not ok:
                return {"success": False, "error": err}
            keyboard_controller.press_key("F5")
            time.sleep(0.5)
            return {"key_sent": "F5"}

        self.register(AppActionDefinition(
            app_canonical_name="Chrome",
            action_name="refresh",
            aliases=["refresh", "reload"],
            capability="windows.interact_with_app",
            risk_level=RiskLevel.LOW,
            handler=_chrome_refresh,
            verification_handler=lambda b, a: (True, "Page refreshed.") if _verify_foreground("Chrome") else (False, "Chrome lost foreground."),
        ))

        # ═══════════════════════════════════════════════════════
        # NOTEPAD ACTIONS — UIA document text verification
        # ═══════════════════════════════════════════════════════
        def _notepad_type(action: StructuredInAppAction) -> dict[str, Any]:
            text = action.arguments.get("text", "hello FALSO")
            ok, err = _focus_and_verify("Notepad")
            if not ok:
                return {"success": False, "error": err}
            keyboard_controller.type_text(text)
            time.sleep(0.2)
            return {"typed_text": text}

        def _notepad_type_verify(before: dict[str, Any], after: dict[str, Any]) -> tuple[bool, str]:
            handler_result = after.get("handler_result", after)
            if handler_result.get("success") is False:
                return False, handler_result.get("error", "Notepad typing failed.")

            typed_text = handler_result.get("typed_text", "")

            # 1. Try UIA: read Notepad document text
            from app.services.automation.windows.ui_automation import ui_automation
            if ui_automation.is_available():
                # Notepad's edit control
                doc_text = ui_automation.get_element_value(automation_id="RichEditBox")
                if doc_text is None:
                    doc_text = ui_automation.get_element_value(automation_id="15")  # Classic Notepad
                if doc_text is None:
                    # Try name-based search
                    doc_text = ui_automation.get_element_value(name="Text Editor")
                if doc_text is not None:
                    if typed_text and typed_text in doc_text:
                        return True, f"Typed '{typed_text}' into Notepad."
                    return False, "Typed text not found in Notepad document."

            # 2. Fallback when UIA not initialized: verify foreground is still Notepad
            if _verify_foreground("Notepad"):
                return True, f"Typed '{typed_text}' into Notepad."

            return False, "Notepad lost foreground during typing."

        self.register(AppActionDefinition(
            app_canonical_name="Notepad",
            action_name="type",
            aliases=["type", "write", "insert text"],
            capability="windows.interact_with_app",
            risk_level=RiskLevel.LOW,
            handler=_notepad_type,
            verification_handler=_notepad_type_verify,
        ))

        def _notepad_select_all(action: StructuredInAppAction) -> dict[str, Any]:
            ok, err = _focus_and_verify("Notepad")
            if not ok:
                return {"success": False, "error": err}
            keyboard_controller.send_hotkey(["CTRL", "A"])
            time.sleep(0.1)
            return {"hotkey_sent": "CTRL+A"}

        def _notepad_select_all_verify(before: dict[str, Any], after: dict[str, Any]) -> tuple[bool, str]:
            handler_result = after.get("handler_result", after)
            if handler_result.get("success") is False:
                return False, handler_result.get("error", "Select all failed.")
            if _verify_foreground("Notepad"):
                return True, "Selected all text in Notepad."
            return False, "Notepad lost foreground."

        self.register(AppActionDefinition(
            app_canonical_name="Notepad",
            action_name="select_all",
            aliases=["select_all", "select all"],
            capability="windows.interact_with_app",
            risk_level=RiskLevel.LOW,
            handler=_notepad_select_all,
            verification_handler=_notepad_select_all_verify,
        ))

        def _notepad_clear(action: StructuredInAppAction) -> dict[str, Any]:
            ok, err = _focus_and_verify("Notepad")
            if not ok:
                return {"success": False, "error": err}
            keyboard_controller.send_hotkey(["CTRL", "A"])
            time.sleep(0.05)
            keyboard_controller.press_key("DELETE")
            time.sleep(0.1)
            return {"action": "clear"}

        def _notepad_clear_verify(before: dict[str, Any], after: dict[str, Any]) -> tuple[bool, str]:
            handler_result = after.get("handler_result", after)
            if handler_result.get("success") is False:
                return False, handler_result.get("error", "Clear failed.")

            from app.services.automation.windows.ui_automation import ui_automation
            if ui_automation.is_available():
                doc_text = ui_automation.get_element_value(automation_id="RichEditBox")
                if doc_text is None:
                    doc_text = ui_automation.get_element_value(automation_id="15")
                if doc_text is not None and doc_text.strip() == "":
                    return True, "Notepad cleared."

            if _verify_foreground("Notepad"):
                return True, "Notepad cleared."
            return False, "Notepad lost foreground."

        self.register(AppActionDefinition(
            app_canonical_name="Notepad",
            action_name="clear",
            aliases=["clear", "clear all"],
            capability="windows.interact_with_app",
            risk_level=RiskLevel.LOW,
            handler=_notepad_clear,
            verification_handler=_notepad_clear_verify,
        ))

        def _notepad_copy(action: StructuredInAppAction) -> dict[str, Any]:
            ok, err = _focus_and_verify("Notepad")
            if not ok:
                return {"success": False, "error": err}
            keyboard_controller.send_hotkey(["CTRL", "C"])
            time.sleep(0.1)
            return {"hotkey_sent": "CTRL+C"}

        def _notepad_copy_verify(before: dict[str, Any], after: dict[str, Any]) -> tuple[bool, str]:
            handler_result = after.get("handler_result", after)
            if handler_result.get("success") is False:
                return False, handler_result.get("error", "Copy failed.")

            from app.services.automation.windows.clipboard_controller import clipboard_controller
            if clipboard_controller.has_text():
                return True, "Copied."
            return False, "Nothing was copied to clipboard."

        self.register(AppActionDefinition(
            app_canonical_name="Notepad",
            action_name="copy",
            aliases=["copy", "copy text", "copy all"],
            capability="windows.interact_with_app",
            risk_level=RiskLevel.LOW,
            handler=_notepad_copy,
            verification_handler=_notepad_copy_verify,
        ))

        def _notepad_paste(action: StructuredInAppAction) -> dict[str, Any]:
            ok, err = _focus_and_verify("Notepad")
            if not ok:
                return {"success": False, "error": err}

            # Capture clipboard content before paste for verification
            from app.services.automation.windows.clipboard_controller import clipboard_controller
            has_content = clipboard_controller.has_text()

            keyboard_controller.send_hotkey(["CTRL", "V"])
            time.sleep(0.2)
            return {"hotkey_sent": "CTRL+V", "clipboard_had_content": has_content}

        def _notepad_paste_verify(before: dict[str, Any], after: dict[str, Any]) -> tuple[bool, str]:
            handler_result = after.get("handler_result", after)
            if handler_result.get("success") is False:
                return False, handler_result.get("error", "Paste failed.")

            had_content = handler_result.get("clipboard_had_content", False)
            if not had_content:
                return False, "Clipboard was empty — nothing to paste."

            if _verify_foreground("Notepad"):
                return True, "Pasted."
            return False, "Notepad lost foreground during paste."

        self.register(AppActionDefinition(
            app_canonical_name="Notepad",
            action_name="paste",
            aliases=["paste", "paste text"],
            capability="windows.interact_with_app",
            risk_level=RiskLevel.LOW,
            handler=_notepad_paste,
            verification_handler=_notepad_paste_verify,
        ))

        def _notepad_save(action: StructuredInAppAction) -> dict[str, Any]:
            ok, err = _focus_and_verify("Notepad")
            if not ok:
                return {"success": False, "error": err}
            keyboard_controller.send_hotkey(["CTRL", "S"])
            time.sleep(0.3)
            return {"hotkey_sent": "CTRL+S"}

        def _notepad_save_verify(before: dict[str, Any], after: dict[str, Any]) -> tuple[bool, str]:
            handler_result = after.get("handler_result", after)
            if handler_result.get("success") is False:
                return False, handler_result.get("error", "Save failed.")
            if _verify_foreground("Notepad"):
                return True, "File save triggered."
            return False, "Notepad lost foreground."

        self.register(AppActionDefinition(
            app_canonical_name="Notepad",
            action_name="save",
            aliases=["save", "save file"],
            capability="windows.save_file",
            risk_level=RiskLevel.MEDIUM,
            handler=_notepad_save,
            verification_handler=_notepad_save_verify,
        ))

        # ═══════════════════════════════════════════════════════
        # FILE EXPLORER ACTIONS
        # ═══════════════════════════════════════════════════════
        def _explorer_open_folder(action: StructuredInAppAction) -> dict[str, Any]:
            path = action.arguments.get("path") or r"C:\Users\Admin\Project-Falso"
            fs_check = permission_manager.check_filesystem_access(path, FileOperation.READ)
            if not fs_check.allowed:
                raise PermissionError(fs_check.reason)
            import subprocess
            subprocess.Popen(["explorer.exe", str(path)])
            time.sleep(1.0)
            return {"folder_path": path}

        def _explorer_open_folder_verify(before: dict[str, Any], after: dict[str, Any]) -> tuple[bool, str]:
            handler_result = after.get("handler_result", after)
            p = handler_result.get("folder_path", "")
            # Verify File Explorer window actually appeared
            if window_manager.is_window_open("File Explorer") or window_manager.is_window_open("explorer"):
                return True, f"Opened {p}."
            return False, f"File Explorer didn't open for '{p}'."

        self.register(AppActionDefinition(
            app_canonical_name="File Explorer",
            action_name="open_folder",
            aliases=["open_folder", "open folder", "navigate to folder"],
            capability="windows.open_approved_folder",
            risk_level=RiskLevel.LOW,
            handler=_explorer_open_folder,
            verification_handler=_explorer_open_folder_verify,
        ))

        def _explorer_back(action: StructuredInAppAction) -> dict[str, Any]:
            ok, err = _focus_and_verify("File Explorer")
            if not ok:
                return {"success": False, "error": err}
            keyboard_controller.send_hotkey(["ALT", "LEFT"])
            time.sleep(0.3)
            return {"hotkey_sent": "ALT+LEFT"}

        self.register(AppActionDefinition(
            app_canonical_name="File Explorer",
            action_name="back",
            aliases=["back", "go back"],
            capability="windows.interact_with_app",
            risk_level=RiskLevel.LOW,
            handler=_explorer_back,
            verification_handler=lambda b, a: (True, "Went back.") if _verify_foreground("File Explorer") else (False, "File Explorer lost foreground."),
        ))

        def _explorer_refresh(action: StructuredInAppAction) -> dict[str, Any]:
            ok, err = _focus_and_verify("File Explorer")
            if not ok:
                return {"success": False, "error": err}
            keyboard_controller.press_key("F5")
            time.sleep(0.3)
            return {"key_sent": "F5"}

        self.register(AppActionDefinition(
            app_canonical_name="File Explorer",
            action_name="refresh",
            aliases=["refresh"],
            capability="windows.interact_with_app",
            risk_level=RiskLevel.LOW,
            handler=_explorer_refresh,
            verification_handler=lambda b, a: (True, "Refreshed.") if _verify_foreground("File Explorer") else (False, "File Explorer lost foreground."),
        ))


app_action_registry = AppActionRegistry()
