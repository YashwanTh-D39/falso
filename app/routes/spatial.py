"""Spatial REST API routes for FALSO Spatial OS.

Endpoints for files, system stats, process management, and confirmation tokens.
"""

import os
import psutil
from pathlib import Path
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel

from app.services.system_monitor import system_monitor
from app.services.filesystem_indexer import filesystem_indexer
from app.services.permission_service import permission_service

router = APIRouter(prefix="/api/v1/spatial", tags=["spatial"])


class ActionRequest(BaseModel):
    target_path: Optional[str] = None
    pid: Optional[int] = None
    new_name: Optional[str] = None


class ConfirmRequest(BaseModel):
    token: str


@router.get("/system")
async def get_system_metrics():
    """Returns real-time system resource metrics."""
    return system_monitor.get_system_stats()


@router.get("/processes")
async def get_running_processes(limit: int = Query(default=30, ge=1, le=100)):
    """Returns top running processes sorted by CPU and memory."""
    return system_monitor.get_running_processes(limit=limit)


@router.get("/usb")
async def get_usb_devices():
    """Returns connected USB hardware devices."""
    return system_monitor.get_usb_devices()


@router.get("/files/recent")
async def get_recent_files(limit: int = Query(default=30, ge=1, le=100)):
    """Returns recently modified indexed files."""
    return filesystem_indexer.get_recent(limit=limit)


@router.get("/files/search")
async def search_files(q: str = Query(..., min_length=1), limit: int = Query(default=30, ge=1, le=100)):
    """Performs FTS5 search on indexed files."""
    return filesystem_indexer.search(q, limit=limit)


@router.post("/files/open")
async def open_file(req: ActionRequest):
    """Opens a file or folder using the default OS application."""
    if not req.target_path:
        raise HTTPException(status_code=400, detail="Target path required.")
    
    if not permission_service.is_path_allowed(req.target_path):
        raise HTTPException(status_code=403, detail="Path access denied. Not in allowed directories.")
    
    p = Path(req.target_path)
    if not p.exists():
        raise HTTPException(status_code=404, detail="File or directory does not exist.")

    try:
        if os.name == 'nt':
            os.startfile(str(p))
        else:
            import subprocess
            subprocess.Popen(['xdg-open', str(p)])
        return {"status": "success", "message": f"Opened {p.name}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to open file: {e}")


@router.post("/files/request-delete")
async def request_delete_file(req: ActionRequest):
    """Generates a confirmation token for deleting a file."""
    if not req.target_path:
        raise HTTPException(status_code=400, detail="Target path required.")
    if not permission_service.is_path_allowed(req.target_path):
        raise HTTPException(status_code=403, detail="Path access denied.")
    
    token = permission_service.create_confirmation_token("delete_file", req.target_path)
    return {"token": token, "action": "delete_file", "target_path": req.target_path, "requires_confirmation": True}


@router.post("/processes/request-kill")
async def request_kill_process(req: ActionRequest):
    """Generates a confirmation token for killing a process."""
    if not req.pid:
        raise HTTPException(status_code=400, detail="Process PID required.")
    
    token = permission_service.create_confirmation_token("kill_process", str(req.pid), {"pid": req.pid})
    return {"token": token, "action": "kill_process", "pid": req.pid, "requires_confirmation": True}


@router.post("/confirm")
async def confirm_action(req: ConfirmRequest):
    """Executes a token-confirmed sensitive action (delete file, kill process, etc.)."""
    action_data = permission_service.confirm_token(req.token)
    if not action_data:
        raise HTTPException(status_code=400, detail="Invalid or expired confirmation token.")
    
    action = action_data["action"]
    target = action_data["target_path"]

    if action == "delete_file":
        try:
            p = Path(target)
            if p.exists():
                # Send to send2trash if available, or remove
                try:
                    import send2trash
                    send2trash.send2trash(str(p))
                except ImportError:
                    if p.is_file():
                        p.unlink()
                    elif p.is_dir():
                        import shutil
                        shutil.rmtree(str(p))
                filesystem_indexer.db_manager.remove_file(str(p.resolve()))
                return {"status": "success", "message": f"Deleted {p.name}"}
            else:
                raise HTTPException(status_code=404, detail="File no longer exists.")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to delete: {e}")

    elif action == "kill_process":
        pid = action_data["metadata"].get("pid")
        try:
            proc = psutil.Process(pid)
            proc.terminate()
            return {"status": "success", "message": f"Terminated process {pid}"}
        except psutil.NoSuchProcess:
            return {"status": "success", "message": f"Process {pid} already stopped."}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to terminate process: {e}")

    raise HTTPException(status_code=400, detail="Unknown action type.")
