import asyncio
import json
import logging
import os
import re
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi import APIRouter, HTTPException, status

from app.schemas.conversations import Conversation

logger = logging.getLogger(__name__)

CHATS_DIR = Path(__file__).resolve().parent.parent.parent / "chats"
CHATS_DIR.mkdir(parents=True, exist_ok=True)

# All chat-file I/O (read/write/replace/unlink, plus the listing's N reads)
# runs here: files are small, the lane is bounded, and the event loop plus the
# default thread pool stay untouched.
_CHAT_EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="falso-chats")

# Serializes concurrent saves of the same conversation. Without it,
# os.replace races on Windows (sharing violation -> PermissionError -> 500)
# when two saves land at once.
_WRITE_LOCK = threading.Lock()

# Safe charset only: alphanumeric, dash, underscore. Rejects any path traversal
# attempt (dots, slashes, backslashes) before it reaches the filesystem.
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")

router = APIRouter(prefix="/api/v1/conversations", tags=["Conversations"])


def _validate_conv_id(conv_id: str) -> str:
    if not _SAFE_ID.fullmatch(conv_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid conversation id",
        )
    return conv_id


def _chat_path(conv_id: str) -> Path:
    return CHATS_DIR / f"{conv_id}.json"


def _read_file(conv_id: str) -> dict | None:
    if not _SAFE_ID.fullmatch(conv_id):
        return None
    path = _chat_path(conv_id)
    if not path.exists():
        return None
    try:
        val = json.loads(path.read_text(encoding="utf-8"))
        return val if isinstance(val, dict) else None
    except (OSError, ValueError):
        logger.warning("Unreadable conversation file: %s", path)
        return None


def _replace_with_retry(tmp: Path, target: Path) -> None:
    """Atomic replace with retries for transient Windows sharing violations
    (target momentarily open by a concurrent reader)."""
    for attempt in range(3):
        try:
            os.replace(tmp, target)
            return
        except PermissionError:
            if attempt == 2:
                raise
            time.sleep(0.05 * (attempt + 1))


def _write_file(conv_id: str, data: dict) -> None:
    if not _SAFE_ID.fullmatch(conv_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid conversation id",
        )
    path = _chat_path(conv_id)
    tmp = CHATS_DIR / f".{conv_id}.{uuid.uuid4().hex}.tmp"
    try:
        tmp.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        with _WRITE_LOCK:
            _replace_with_retry(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink()


def _delete_file(conv_id: str) -> None:
    if not _SAFE_ID.fullmatch(conv_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid conversation id",
        )
    path = _chat_path(conv_id)
    try:
        path.unlink(missing_ok=True)
    except OSError:
        logger.warning("Could not delete conversation file: %s", path)


def _mtime_or_zero(path: Path) -> float:
    # A file can vanish between glob() and stat() when a delete lands
    # concurrently; a vanished file simply sorts first and is skipped by
    # _read_file below instead of crashing the whole listing.
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


def _list_files(*, offset: int = 0, limit: int = 50) -> list[dict]:
    items: list[dict] = []
    for f in sorted(
        CHATS_DIR.glob("*.json"),
        key=_mtime_or_zero,
        reverse=True,
    ):
        data = _read_file(f.stem)
        if data is None:
            continue
        conv_id = data.get("id")
        if not conv_id or not _SAFE_ID.fullmatch(str(conv_id)):
            continue
        items.append({
            "id": conv_id,
            "title": data.get("title", "New Chat"),
            "createdAt": data.get("createdAt", ""),
            "updatedAt": data.get("updatedAt", ""),
        })
    return items[offset:offset + limit]


@router.get("/")
async def list_conversations(page: int = 1, per_page: int = 50):
    page = max(page, 1)
    if per_page < 1:
        per_page = 1
    elif per_page > 200:
        per_page = 200
    offset = (page - 1) * per_page
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        _CHAT_EXECUTOR, lambda: _list_files(offset=offset, limit=per_page)
    )



@router.get("/{conv_id}")
async def get_conversation(conv_id: str):
    _validate_conv_id(conv_id)
    loop = asyncio.get_running_loop()
    data = await loop.run_in_executor(_CHAT_EXECUTOR, _read_file, conv_id)
    if data is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )
    return data


@router.post("/")
async def save_conversation(conv: Conversation):
    _validate_conv_id(conv.id)
    loop = asyncio.get_running_loop()
    try:
        await loop.run_in_executor(_CHAT_EXECUTOR, _write_file, conv.id, conv.model_dump())
    except OSError:
        logger.exception("Failed to save conversation %s", conv.id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Storage error",
        )
    return {"ok": True}


@router.delete("/{conv_id}")
async def delete_conversation(conv_id: str):
    _validate_conv_id(conv_id)
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(_CHAT_EXECUTOR, _delete_file, conv_id)
    return {"ok": True}
