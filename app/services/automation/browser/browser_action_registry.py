"""
Browser Action Registry Service for FALSO (FALSO 4.6 & 4.7).

Defines structured browser actions, capabilities, risk levels, and handlers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


class ActionRiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass
class BrowserActionDefinition:
    action_name: str
    aliases: List[str]
    capability: str
    risk_level: ActionRiskLevel
    description: str
    requires_confirmation: bool = False


@dataclass
class StructuredBrowserAction:
    action: str
    target: str = ""
    arguments: Dict[str, Any] = field(default_factory=dict)
    capability: str = "browser.interact"
    risk_level: ActionRiskLevel = ActionRiskLevel.LOW
    requires_confirmation: bool = False


class BrowserActionRegistry:
    """Registry for all approved FALSO browser and form automation actions."""

    def __init__(self) -> None:
        self._actions: Dict[str, BrowserActionDefinition] = {}
        self._register_default_actions()

    def _register_default_actions(self) -> None:
        defaults = [
            BrowserActionDefinition(
                action_name="open_browser",
                aliases=["open browser", "launch browser", "start chrome", "open chrome"],
                capability="browser.open",
                risk_level=ActionRiskLevel.LOW,
                description="Open or focus web browser",
            ),
            BrowserActionDefinition(
                action_name="new_tab",
                aliases=["new tab", "open a new tab", "create new tab", "open tab"],
                capability="browser.interact",
                risk_level=ActionRiskLevel.LOW,
                description="Open a new browser tab",
            ),
            BrowserActionDefinition(
                action_name="close_tab",
                aliases=["close tab", "close current tab", "close this tab"],
                capability="browser.interact",
                risk_level=ActionRiskLevel.LOW,
                description="Close active browser tab",
            ),
            BrowserActionDefinition(
                action_name="navigate",
                aliases=["navigate", "go to", "open url", "visit"],
                capability="browser.navigate",
                risk_level=ActionRiskLevel.LOW,
                description="Navigate to target URL or website",
            ),
            BrowserActionDefinition(
                action_name="search",
                aliases=["search google", "search", "search for", "google search"],
                capability="browser.navigate",
                risk_level=ActionRiskLevel.LOW,
                description="Perform a web search",
            ),
            BrowserActionDefinition(
                action_name="back",
                aliases=["go back", "back", "previous page"],
                capability="browser.interact",
                risk_level=ActionRiskLevel.LOW,
                description="Navigate back in history",
            ),
            BrowserActionDefinition(
                action_name="forward",
                aliases=["go forward", "forward", "next page"],
                capability="browser.interact",
                risk_level=ActionRiskLevel.LOW,
                description="Navigate forward in history",
            ),
            BrowserActionDefinition(
                action_name="refresh",
                aliases=["refresh", "reload", "reload page"],
                capability="browser.interact",
                risk_level=ActionRiskLevel.LOW,
                description="Refresh active page",
            ),
            BrowserActionDefinition(
                action_name="scroll",
                aliases=["scroll down", "scroll up", "scroll to bottom", "scroll page"],
                capability="browser.interact",
                risk_level=ActionRiskLevel.LOW,
                description="Scroll page content",
            ),
            BrowserActionDefinition(
                action_name="click",
                aliases=["click", "press button", "follow link", "open result", "click result"],
                capability="browser.interact",
                risk_level=ActionRiskLevel.LOW,
                description="Click interactive element",
            ),
            BrowserActionDefinition(
                action_name="type",
                aliases=["type", "enter text", "fill text", "input text"],
                capability="browser.fill_safe_field",
                risk_level=ActionRiskLevel.LOW,
                description="Type text into active input field",
            ),
            BrowserActionDefinition(
                action_name="select",
                aliases=["select", "choose", "pick option", "select dropdown"],
                capability="browser.interact",
                risk_level=ActionRiskLevel.LOW,
                description="Select option from dropdown or select list",
            ),
            BrowserActionDefinition(
                action_name="focus",
                aliases=["focus", "focus element", "focus field"],
                capability="browser.interact",
                risk_level=ActionRiskLevel.LOW,
                description="Focus target interactive element",
            ),
            BrowserActionDefinition(
                action_name="read_page",
                aliases=["read page", "get page text", "tell me page title", "read title"],
                capability="browser.read_form",
                risk_level=ActionRiskLevel.LOW,
                description="Read title, visible text, or content of active page",
            ),
            BrowserActionDefinition(
                action_name="find_element",
                aliases=["find element", "locate button", "find link", "find input"],
                capability="browser.interact",
                risk_level=ActionRiskLevel.LOW,
                description="Find semantic element on page",
            ),
            BrowserActionDefinition(
                action_name="fill_form",
                aliases=["fill form", "fill the form", "populate form", "fill details"],
                capability="browser.fill_safe_field",
                risk_level=ActionRiskLevel.MEDIUM,
                description="Fill structured form fields",
            ),
            BrowserActionDefinition(
                action_name="submit_form",
                aliases=["submit form", "submit it", "click submit", "press submit"],
                capability="browser.submit_form",
                risk_level=ActionRiskLevel.HIGH,
                requires_confirmation=True,
                description="Submit filled form (requires user confirmation)",
            ),
        ]
        for act in defaults:
            self._actions[act.action_name] = act

    def get_action_definition(self, name: str) -> Optional[BrowserActionDefinition]:
        return self._actions.get(name.lower())

    def resolve_natural_language_action(self, phrase: str) -> Optional[StructuredBrowserAction]:
        p_lower = phrase.lower().strip()

        # Submit form
        if "submit" in p_lower:
            return StructuredBrowserAction(
                action="submit_form",
                target="form",
                capability="browser.submit_form",
                risk_level=ActionRiskLevel.HIGH,
                requires_confirmation=True,
            )

        # Fill form
        if "fill" in p_lower and "form" in p_lower:
            return StructuredBrowserAction(
                action="fill_form",
                target="form",
                capability="browser.fill_safe_field",
                risk_level=ActionRiskLevel.MEDIUM,
            )

        # Navigation
        if p_lower.startswith("go to ") or p_lower.startswith("open http") or p_lower.startswith("visit "):
            target = p_lower.replace("go to ", "").replace("open ", "").replace("visit ", "").strip()
            return StructuredBrowserAction(
                action="navigate",
                target=target,
                capability="browser.navigate",
                risk_level=ActionRiskLevel.LOW,
            )

        # Search
        if p_lower.startswith("search ") or "search google" in p_lower:
            target = p_lower.replace("search google for ", "").replace("search for ", "").replace("search ", "").strip()
            return StructuredBrowserAction(
                action="search",
                target=target,
                capability="browser.navigate",
                risk_level=ActionRiskLevel.LOW,
            )

        # New tab / close tab
        if "new tab" in p_lower:
            return StructuredBrowserAction(action="new_tab", capability="browser.interact")
        if "close tab" in p_lower:
            return StructuredBrowserAction(action="close_tab", capability="browser.interact")

        # Scroll
        if "scroll" in p_lower:
            direction = "bottom" if "bottom" in p_lower else ("up" if "up" in p_lower else "down")
            return StructuredBrowserAction(
                action="scroll",
                arguments={"direction": direction},
                capability="browser.interact",
            )

        # Read page / title
        if any(w in p_lower for w in ("read page", "page title", "tell me the title", "what is the title")):
            return StructuredBrowserAction(action="read_page", capability="browser.read_form")

        # Generic Match
        for defn in self._actions.values():
            if any(alias in p_lower for alias in defn.aliases):
                return StructuredBrowserAction(
                    action=defn.action_name,
                    capability=defn.capability,
                    risk_level=defn.risk_level,
                    requires_confirmation=defn.requires_confirmation,
                )

        return None


browser_action_registry = BrowserActionRegistry()
