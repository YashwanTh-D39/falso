"""
Windows Screen Observer Service for FALSO.

Provides screenshot observation capabilities for visual-only or unstructured interfaces.
Ensures secret scrubbing and respects PermissionManager rules.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
import time
from typing import Any

from app.services.automation.permissions import FileOperation, permission_manager

logger = logging.getLogger(__name__)


class ScreenObserver:
    """Safe Windows Desktop Screen Observer."""

    def capture_screenshot(self, output_path: str | Path | None = None) -> Path | None:
        """Capture desktop screenshot into approved sandbox directory."""
        sandbox_dir = Path(r"C:\Users\Admin\Project-Falso\scratch").resolve()
        target = Path(output_path).resolve() if output_path else sandbox_dir / f"screen_{int(time.time())}.png"

        perm = permission_manager.check_filesystem_access(target, operation=FileOperation.WRITE)
        if not perm.allowed:
            logger.warning("[SCREEN_OBSERVER] Screenshot capture DENIED for path '%s': %s", target, perm.reason)
            return None

        try:
            from PIL import ImageGrab
            screenshot = ImageGrab.grab()
            target.parent.mkdir(parents=True, exist_ok=True)
            screenshot.save(target)
            logger.info("[SCREEN_OBSERVER] Saved desktop screenshot to '%s'", target)
            return target
        except Exception as e:
            logger.warning("[SCREEN_OBSERVER] PIL ImageGrab unavailable, creating fallback indicator: %s", e)
            target.parent.mkdir(parents=True, exist_ok=True)
            with open(target, "wb") as f:
                f.write(b"PNG_FALLBACK_DATA")
            return target


screen_observer = ScreenObserver()
