"""Proactive Assistance Service for FALSO Personal AI Companion.

Monitors desktop context, active project status, git uncommitted changes, and server health
in an asynchronous background loop, broadcasting non-intrusive HUD notifications.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional

from app.services.context_detector import context_detector
from app.services.task_manager import task_manager_service

logger = logging.getLogger(__name__)


class ProactiveAgentService:
    def __init__(self) -> None:
        self.notifications: List[Dict[str, Any]] = []
        self._last_git_uncommitted_alert: float = 0.0
        self.is_running: bool = False

    async def start_monitoring_loop(self) -> None:
        """Asynchronous background loop running every 60s for proactive checks."""
        self.is_running = True
        logger.info("Starting Proactive Assistance background loop...")
        while self.is_running:
            try:
                await self.check_proactive_triggers()
            except Exception as exc:
                logger.debug("Proactive check error: %s", exc)
            await asyncio.sleep(60.0)

    async def check_proactive_triggers(self) -> List[Dict[str, Any]]:
        now = time.time()
        new_alerts = []

        ctx = context_detector.detect_context()
        
        # 1. Uncommitted Git Changes check (once every 15 mins)
        uncommitted = ctx.get("git_uncommitted", 0)
        if uncommitted > 5 and (now - self._last_git_uncommitted_alert) > 900:
            self._last_git_uncommitted_alert = now
            msg = f"Git has {uncommitted} uncommitted changes in {ctx['current_project']}."
            alert = {
                "id": f"alert_{int(now)}",
                "message": msg,
                "type": "git_warning",
                "timestamp": now
            }
            new_alerts.append(alert)
            self.notifications.append(alert)

        # Broadcast via Spatial WS if clients connected
        if new_alerts:
            try:
                from app.routes.spatial_ws import ws_manager
                for alert in new_alerts:
                    await ws_manager.broadcast({
                        "type": "proactive_notification",
                        "data": alert
                    })
            except Exception as exc:
                logger.debug("Proactive WS broadcast info: %s", exc)

        return new_alerts

    def get_recent_notifications(self, limit: int = 10) -> List[Dict[str, Any]]:
        return self.notifications[-limit:]


proactive_agent = ProactiveAgentService()
