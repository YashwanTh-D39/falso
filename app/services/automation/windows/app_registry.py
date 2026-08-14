"""
Normalized Application Identity Registry for FALSO.

Maps canonical application names to aliases, process names, executable paths,
and window title/class patterns. Used for accurate window and process targeting.
Enforces that alias resolution NEVER bypasses PermissionManager allowlists.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ApplicationIdentity:
    canonical_name: str
    aliases: list[str]
    process_names: list[str]
    executable_paths: list[str] = field(default_factory=list)
    window_title_patterns: list[str] = field(default_factory=list)
    window_class_patterns: list[str] = field(default_factory=list)


# Registry of approved/supported applications
_APP_REGISTRY: dict[str, ApplicationIdentity] = {
    "Calculator": ApplicationIdentity(
        canonical_name="Calculator",
        aliases=["calculator", "calc", "calc.exe", "calculatorapp"],
        process_names=["calc.exe", "calculator.exe", "calculatorapp.exe", "calc"],
        executable_paths=["calc.exe"],
        window_title_patterns=["calculator", "calc"],
    ),
    "Chrome": ApplicationIdentity(
        canonical_name="Chrome",
        aliases=["chrome", "google chrome", "chrome.exe", "browser"],
        process_names=["chrome.exe", "chrome"],
        executable_paths=[
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
        ],
        window_title_patterns=["chrome", "google chrome"],
    ),
    "Claude": ApplicationIdentity(
        canonical_name="Claude",
        aliases=["claude", "claude desktop", "anthropic claude", "claude.exe", "claude ai"],
        process_names=["claude.exe", "claude", "anthropic claude.exe"],
        executable_paths=[
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\Claude\Claude.exe"),
            os.path.expandvars(r"%LOCALAPPDATA%\AnthropicClaude\Claude.exe"),
            os.path.expandvars(r"%APPDATA%\Claude\Claude.exe"),
            "Claude.exe",
        ],
        window_title_patterns=["claude", "anthropic claude", "claude desktop"],
    ),
    "Notepad": ApplicationIdentity(
        canonical_name="Notepad",
        aliases=["notepad", "notepad.exe", "editor", "text editor"],
        process_names=["notepad.exe", "notepad"],
        executable_paths=["notepad.exe"],
        window_title_patterns=["notepad"],
    ),
    "File Explorer": ApplicationIdentity(
        canonical_name="File Explorer",
        aliases=["file explorer", "explorer", "windows explorer", "explorer.exe", "this pc"],
        process_names=["explorer.exe", "explorer"],
        executable_paths=["explorer.exe"],
        window_title_patterns=["file explorer", "explorer", "this pc"],
    ),
    "VS Code": ApplicationIdentity(
        canonical_name="VS Code",
        aliases=["vs code", "vscode", "code", "code.exe", "microsoft vs code"],
        process_names=["code.exe", "code"],
        executable_paths=[
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\Microsoft VS Code\Code.exe"),
            r"C:\Program Files\Microsoft VS Code\Code.exe",
        ],
        window_title_patterns=["visual studio code", "vs code", "code"],
    ),
}


class AppRegistry:
    """Registry facade for query alias resolution and target matching."""

    @staticmethod
    def resolve(query: str) -> ApplicationIdentity | None:
        """Resolve a query or alias to its canonical ApplicationIdentity."""
        if not query:
            return None
        q = query.lower().strip()

        # Direct match against canonical names
        for canonical, app in _APP_REGISTRY.items():
            if q == canonical.lower():
                return app

        # Match against aliases
        for app in _APP_REGISTRY.values():
            if any(alias == q or alias in q for alias in app.aliases):
                return app

        # Fallback substring match on canonical name
        for app in _APP_REGISTRY.values():
            if app.canonical_name.lower() in q:
                return app

        return None

    @staticmethod
    def get_title_patterns(query: str) -> list[str]:
        app = AppRegistry.resolve(query)
        if app and app.window_title_patterns:
            return app.window_title_patterns
        clean = query.lower().strip()
        return [clean]

    @staticmethod
    def get_process_names(query: str) -> list[str]:
        app = AppRegistry.resolve(query)
        if app and app.process_names:
            return app.process_names
        clean = query.lower().strip()
        return [clean if clean.endswith(".exe") else f"{clean}.exe", clean]


app_registry = AppRegistry()
