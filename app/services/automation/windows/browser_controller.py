"""
Windows Browser Controller Service for FALSO.

Goal-oriented browser navigation, search, and localhost verification.
Integrated with PermissionManager Browser Capabilities.
"""

from __future__ import annotations

import logging
import os
import subprocess
import time
from typing import Any

from app.services.automation.permissions import permission_manager
from app.services.automation.windows.process_manager import process_manager
from app.services.automation.windows.window_manager import window_manager

logger = logging.getLogger(__name__)


class BrowserController:
    """Safe Windows Browser Automation Controller."""

    def open_browser(self, url: str = "http://localhost:8000") -> bool:
        """Open or focus browser and navigate to target URL."""
        perm = permission_manager.check_capability("browser.navigate", target=url)
        if not perm.allowed:
            logger.warning("[BROWSER] Navigation DENIED for URL '%s': %s", url, perm.reason)
            return False

        # If browser window is already open, focus it
        if window_manager.is_window_open("chrome") or window_manager.is_window_open("edge"):
            window_manager.focus_window("chrome") or window_manager.focus_window("edge")

        # Launch process with URL
        launch_res = process_manager.launch_app("chrome", args=[url])
        launched = launch_res.get("verified", False) if isinstance(launch_res, dict) else bool(launch_res)
        if not launched:
            launch_res = process_manager.launch_app("msedge", args=[url])
            launched = launch_res.get("verified", False) if isinstance(launch_res, dict) else bool(launch_res)

        logger.info("[BROWSER] Browser navigated to '%s' (success=%s)", url, launched)
        return launched

    def navigate(self, url: str) -> bool:
        return self.open_browser(url)

    def search(self, query: str) -> bool:
        search_url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
        return self.navigate(search_url)


browser_controller = BrowserController()
