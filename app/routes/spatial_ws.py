"""Spatial WebSocket streaming route for FALSO Spatial OS.

Streams real-time system state (CPU, RAM, GPU, processes, recent files) to frontend at ~1-2Hz.
"""

import asyncio
import logging
from typing import Set

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import orjson

from app.services.system_monitor import system_monitor
from app.services.filesystem_indexer import filesystem_indexer

logger = logging.getLogger(__name__)

router = APIRouter(tags=["spatial_ws"])


class SpatialConnectionManager:
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)
        logger.info(f"Spatial WS Client connected. Total: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)
        logger.info(f"Spatial WS Client disconnected. Remaining: {len(self.active_connections)}")

    async def broadcast_payload(self, payload: dict):
        if not self.active_connections:
            return
        
        data_bytes = orjson.dumps(payload)
        dead = []
        for connection in self.active_connections:
            try:
                await connection.send_bytes(data_bytes)
            except Exception:
                dead.append(connection)

        for dead_conn in dead:
            self.disconnect(dead_conn)


ws_manager = SpatialConnectionManager()


@router.websocket("/ws/spatial")
async def spatial_websocket_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            # Handle incoming ping / messages
            msg = await websocket.receive_text()
            if msg == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception as e:
        logger.warning(f"Spatial WS error: {e}")
        ws_manager.disconnect(websocket)


import xxhash

_last_payload_hash: bytes = b""


async def spatial_broadcaster_loop():
    """Event & change-driven background broadcast loop for spatial telemetry."""
    global _last_payload_hash
    logger.info("Starting Spatial WS telemetry broadcaster background task...")
    while True:
        try:
            # If no active connections, do NOT poll system stats or consume CPU
            if not ws_manager.active_connections:
                await asyncio.sleep(2.0)
                continue

            stats = system_monitor.get_system_stats()
            processes = system_monitor.get_running_processes(limit=15)
            recent_files = filesystem_indexer.get_recent(limit=25)
            usb_devices = system_monitor.get_usb_devices()
            browser_tabs = system_monitor.get_browser_tabs()

            from app.services.context_detector import context_detector
            git_ctx = context_detector.detect_context()

            context_data = {
                "project": git_ctx.get("current_project", "Project-Falso"),
                "folder": git_ctx.get("current_folder", "c:/Users/Admin/Project-Falso"),
                "active_window": stats.get("user_context", {}).get("active_window", "Project-Falso"),
                "active_file": recent_files[0]["name"] if recent_files else "main.py",
                "git_branch": git_ctx.get("git_branch", "main"),
                "git_uncommitted": git_ctx.get("git_uncommitted", 0),
                "running_ide": git_ctx.get("running_ide", "VS Code")
            }

            # Construct diffable payload summary (omit exact timestamp from hash check)
            summary_state = {
                "cpu_total": stats["cpu"]["total_percent"],
                "ram_percent": stats["ram"]["percent"],
                "proc_count": len(processes),
                "top_proc_pid": processes[0]["pid"] if processes else 0,
                "top_proc_cpu": processes[0]["cpu_percent"] if processes else 0,
                "files_count": len(recent_files),
                "top_file_mod": recent_files[0]["modified_at"] if recent_files else 0,
                "tabs_count": len(browser_tabs),
                "active_win": context_data["active_window"]
            }
            
            state_bytes = orjson.dumps(summary_state)
            current_hash = xxhash.xxh64_digest(state_bytes)

            # Only broadcast if state changed or first connection frame
            if current_hash != _last_payload_hash:
                _last_payload_hash = current_hash
                payload = {
                    "type": "SPATIAL_STATE_UPDATE",
                    "system": stats,
                    "context": context_data,
                    "processes": processes,
                    "browser_tabs": browser_tabs,
                    "files": recent_files,
                    "usb": usb_devices,
                    "timestamp": stats.get("timestamp")
                }
                await ws_manager.broadcast_payload(payload)
        except Exception as e:
            logger.error(f"Error in spatial broadcaster loop: {e}")
        
        await asyncio.sleep(1.5)
