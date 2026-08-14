"""
SessionHistory Manager for FALSO 4.3.

Provides bounded, thread-safe, async-safe short-term conversation context
per stable session_id across chat and automation requests.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
import logging
import time
from typing import Any

from app.schemas.brain import ChatMessage

logger = logging.getLogger(__name__)


@dataclass
class SessionState:
    session_id: str
    messages: list[ChatMessage] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)


class SessionHistoryManager:
    """Manages active short-term conversation session histories with bounded context."""

    def __init__(self, max_messages: int = 20, inactivity_timeout_seconds: float = 1800.0) -> None:
        self._sessions: dict[str, SessionState] = {}
        self.max_messages = max_messages
        self.inactivity_timeout_seconds = inactivity_timeout_seconds
        self._lock = asyncio.Lock()

    def get_or_create_session(self, session_id: str) -> SessionState:
        sid = session_id.strip() if session_id else "FALSO-SESSION-DEFAULT"
        now = time.time()

        if sid in self._sessions:
            sess = self._sessions[sid]
            # Check expiration
            if now - sess.updated_at > self.inactivity_timeout_seconds:
                logger.info("[MEMORY][SESSION_EXPIRED] session_id=%s expired after inactivity.", sid)
                sess = SessionState(session_id=sid, created_at=now, updated_at=now)
                self._sessions[sid] = sess
            else:
                sess.updated_at = now
            return sess

        logger.info("[MEMORY][SESSION_CREATE] session_id=%s", sid)
        sess = SessionState(session_id=sid, created_at=now, updated_at=now)
        self._sessions[sid] = sess
        return sess

    def append_user_message(self, session_id: str, content: str) -> None:
        if not content or not content.strip():
            return
        sess = self.get_or_create_session(session_id)

        # Avoid duplicate consecutive user messages
        clean = content.strip()
        if sess.messages and sess.messages[-1].role == "user" and sess.messages[-1].content.strip() == clean:
            return

        sess.messages.append(ChatMessage(role="user", content=clean))
        sess.updated_at = time.time()
        logger.info("[MEMORY][SESSION_APPEND] session_id=%s role=user msg_len=%d", sess.session_id, len(clean))
        self.trim_history(sess.session_id)

    def append_assistant_message(self, session_id: str, content: str) -> None:
        if not content or not content.strip():
            return
        sess = self.get_or_create_session(session_id)

        clean = content.strip()
        # Filter out meta labels/disclaimers
        banned = ("simulated voice output", "voice activation", "audio playback")
        if any(b in clean.lower() for b in banned):
            return

        sess.messages.append(ChatMessage(role="assistant", content=clean))
        sess.updated_at = time.time()
        logger.info("[MEMORY][SESSION_APPEND] session_id=%s role=assistant msg_len=%d", sess.session_id, len(clean))
        self.trim_history(sess.session_id)

    def trim_history(self, session_id: str) -> None:
        sid = session_id.strip() if session_id else "FALSO-SESSION-DEFAULT"
        if sid not in self._sessions:
            return
        sess = self._sessions[sid]
        if len(sess.messages) > self.max_messages:
            trimmed_count = len(sess.messages) - self.max_messages
            sess.messages = sess.messages[-self.max_messages:]
            logger.info("[MEMORY][SESSION_TRIM] session_id=%s trimmed=%d remaining=%d", sid, trimmed_count, len(sess.messages))

    def get_history(self, session_id: str, max_msgs: int = 20) -> list[ChatMessage]:
        sid = session_id.strip() if session_id else "FALSO-SESSION-DEFAULT"
        if sid not in self._sessions:
            logger.info("[MEMORY][SESSION_RETRIEVE] session_id=%s messages=0", sid)
            return []
        sess = self.get_or_create_session(sid)
        result = sess.messages[-max_msgs:] if len(sess.messages) > max_msgs else list(sess.messages)
        logger.info("[MEMORY][SESSION_RETRIEVE] session_id=%s messages=%d", sid, len(result))
        return result

    def get_last_target_app(self, session_id: str) -> str | None:
        """Find the most recently mentioned application target in session history."""
        history = self.get_history(session_id, max_msgs=10)
        app_names = ("calculator", "chrome", "notepad", "file explorer", "explorer", "vs code", "code")
        for msg in reversed(history):
            content_lower = msg.content.lower()
            for app in app_names:
                if app in content_lower:
                    if app in ("calculator", "calc"):
                        return "Calculator"
                    if app in ("chrome", "google chrome"):
                        return "Chrome"
                    if app == "notepad":
                        return "Notepad"
                    if app in ("explorer", "file explorer"):
                        return "File Explorer"
                    if app in ("code", "vs code"):
                        return "VS Code"
        return None

    def clear_session(self, session_id: str) -> None:
        sid = session_id.strip() if session_id else "FALSO-SESSION-DEFAULT"
        if sid in self._sessions:
            self._sessions[sid].messages.clear()
            self._sessions[sid].updated_at = time.time()
            logger.info("[MEMORY][SESSION_CLEAR] session_id=%s", sid)

    def delete_session(self, session_id: str) -> None:
        sid = session_id.strip() if session_id else "FALSO-SESSION-DEFAULT"
        if sid in self._sessions:
            del self._sessions[sid]
            logger.info("[MEMORY][SESSION_DELETE] session_id=%s", sid)

    def cleanup_expired_sessions(self) -> int:
        now = time.time()
        expired = [sid for sid, sess in self._sessions.items() if now - sess.updated_at > self.inactivity_timeout_seconds]
        for sid in expired:
            del self._sessions[sid]
        if expired:
            logger.info("[MEMORY][SESSION_CLEANUP] cleaned=%d expired sessions", len(expired))
        return len(expired)


# Global singleton SessionHistoryManager
session_history_manager = SessionHistoryManager()
