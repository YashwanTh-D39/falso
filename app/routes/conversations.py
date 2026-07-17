import json
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, status

from app.schemas.conversations import Conversation

logger = logging.getLogger(__name__)

CHATS_DIR = Path(__file__).resolve().parent.parent.parent / "chats"
CHATS_DIR.mkdir(parents=True, exist_ok=True)

router = APIRouter(prefix="/api/v1/conversations", tags=["Conversations"])


def _read_file(conv_id: str) -> dict | None:
    path = CHATS_DIR / f"{conv_id}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _write_file(conv_id: str, data: dict) -> None:
    path = CHATS_DIR / f"{conv_id}.json"
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def _delete_file(conv_id: str) -> None:
    path = CHATS_DIR / f"{conv_id}.json"
    if path.exists():
        path.unlink()


def _list_files() -> list[dict]:
    items: list[dict] = []
    for f in sorted(
        CHATS_DIR.glob("*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    ):
        data = _read_file(f.stem)
        if data is None:
            continue
        items.append({
            "id": data["id"],
            "title": data.get("title", "New Chat"),
            "createdAt": data.get("createdAt", ""),
            "updatedAt": data.get("updatedAt", ""),
        })
    return items


@router.get("/")
async def list_conversations():
    return _list_files()


@router.get("/{conv_id}")
async def get_conversation(conv_id: str):
    data = _read_file(conv_id)
    if data is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    return data


@router.post("/")
async def save_conversation(conv: Conversation):
    data = conv.model_dump()
    _write_file(conv.id, data)
    return {"ok": True}


@router.delete("/{conv_id}")
async def delete_conversation(conv_id: str):
    _delete_file(conv_id)
    return {"ok": True}
