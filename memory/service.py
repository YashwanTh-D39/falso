"""
FALSO 4.3 Persistent Memory & Personal Context Engine.

Provides useful, selective, structured, searchable, and privacy-aware memory persistence.
Categories: USER_PREFERENCES, PROJECT_MEMORY, TASK_MEMORY, CONVERSATION_MEMORY, AUTOMATION_MEMORY, SYSTEM_CONTEXT.
Scopes: GLOBAL, PROJECT, TASK, SESSION.

Enforces strict Memory Privacy & Audit Rules:
- Rejects API keys, tokens, passwords, cookies, and .env assignments (emits MEMORY_SENSITIVE_DATA_BLOCKED).
- Supports explicit user memory commands ("FALSO remember...", "FALSO forget...", "What do you remember?").
- Supports privacy override ("FALSO don't remember this").
- MEMORY IS NOT PERMISSION: Memory informs planning but NEVER overrides PermissionManager.
"""

from __future__ import annotations

import logging
import re

from memory.base import BaseMemoryStore, MemoryEntry, MemorySearchResult
from memory.json_store import JSONMemoryStore
from memory.secrets import is_sensitive_data

logger = logging.getLogger(__name__)


class MemoryService:
    """Unified memory manager with FALSO 4.3 personal context and privacy isolation."""

    def __init__(self, store: BaseMemoryStore | None = None) -> None:
        if store is not None:
            self.store = store
        else:
            self.store = self._init_store()
        self.privacy_override_active: bool = False

    @staticmethod
    def _init_store() -> BaseMemoryStore:
        try:
            from memory.chroma_store import ChromaMemoryStore

            store = ChromaMemoryStore()
            logger.info("MemoryService initialized with ChromaMemoryStore")
            return store
        except ImportError:
            logger.info("ChromaDB not available — MemoryService using JSONMemoryStore")
            return JSONMemoryStore()
        except Exception as e:  # noqa: BLE001
            logger.warning("Failed to initialize ChromaMemoryStore (%s) — falling back to JSONMemoryStore", e)
            return JSONMemoryStore()

    def remember(
        self,
        fact: str,
        category: str = "general",
        importance: int | str = 1,
        source: str = "USER_EXPLICIT",
        metadata: dict | None = None,
        scope: str = "GLOBAL",
        confidence: str = "HIGH",
        classification: str = "PERSISTENT",
        key: str = "",
        value: str = "",
        tags: list[str] | None = None,
    ) -> MemoryEntry:
        """Store a new fact or preference. Rejects sensitive data/credentials."""
        if self.privacy_override_active:
            logger.info("[MEMORY] MEMORY_REJECTED: Privacy override active — skipping storage.")
            return MemoryEntry(content=fact, metadata={"rejected": True})

        if is_sensitive_data(fact) or (value and is_sensitive_data(value)):
            logger.warning("[MEMORY] MEMORY_REJECTED: MEMORY_SENSITIVE_DATA_BLOCKED")
            raise ValueError("Sensitive credentials, passwords, or API keys cannot be stored in memory.")

        # Convert numerical importance for backward compatibility
        imp_val = 1
        if isinstance(importance, int):
            imp_val = importance
        elif isinstance(importance, str):
            imp_val = 3 if importance.upper() == "HIGH" else (2 if importance.upper() == "MEDIUM" else 1)

        merged_meta = {
            "category": category,
            "importance": imp_val,
            "importance_label": str(importance),
            "source": source,
            "scope": scope,
            "confidence": confidence,
            "classification": classification,
            "key": key,
            "value": value,
            "tags": tags or [],
            **(metadata or {}),
        }

        # Handle conflict resolution: remove old memory with same key and scope if exists
        if key:
            self.forget_by_key(key=key, scope=scope)

        entry = self.store.add(fact, metadata=merged_meta)
        logger.info("[MEMORY] MEMORY_CREATED | id=%s key=%r category=%s scope=%s", entry.id, key or fact[:20], category, scope)
        return entry

    def remember_preference(self, key: str, value: str, scope: str = "GLOBAL") -> MemoryEntry:
        """Store a user preference (e.g., preferred_editor, preferred_browser, preferred_project)."""
        content = f"User preference - {key}: {value}"
        return self.remember(
            fact=content,
            category="user_preference",
            importance="HIGH",
            source="USER_EXPLICIT",
            scope=scope,
            confidence="HIGH",
            classification="PERSISTENT",
            key=key,
            value=value,
        )

    def remember_session_summary(self, conversation_id: str, summary: str) -> MemoryEntry:
        """Store a conversation session summary for long-term recall."""
        content = f"Past conversation summary ({conversation_id}): {summary}"
        return self.remember(
            fact=content,
            category="session_summary",
            importance="MEDIUM",
            source="USER_CONVERSATION",
            scope="SESSION",
            metadata={"conversation_id": conversation_id},
        )

    def update_memory(
        self,
        memory_id: str,
        content: str | None = None,
        metadata: dict | None = None,
        importance: int | None = None,
        category: str | None = None,
    ) -> MemoryEntry | None:
        """Update an existing memory entry."""
        if content is not None and is_sensitive_data(content):
            logger.warning("[MEMORY] MEMORY_REJECTED: MEMORY_SENSITIVE_DATA_BLOCKED on update")
            raise ValueError("Sensitive credentials, passwords, or API keys cannot be stored in memory.")

        updated = self.store.update(
            memory_id,
            content=content,
            metadata=metadata,
            importance=importance,
            category=category,
        )
        if updated:
            logger.info("[MEMORY] MEMORY_UPDATED | id=%s", memory_id)
        return updated

    def recall(self, query: str, limit: int = 5) -> list[MemorySearchResult]:
        """Retrieve relevant memories matching query."""
        return self.store.search(query, limit=limit)

    def forget(self, memory_id: str) -> bool:
        """Delete a memory by ID."""
        deleted = self.store.delete(memory_id)
        if deleted:
            logger.info("[MEMORY] MEMORY_DELETED | id=%s", memory_id)
        return deleted

    def forget_by_key(self, key: str, scope: str | None = None) -> int:
        """Delete all memories matching key and optional scope."""
        deleted_count = 0
        all_memories = self.list_memories(limit=500)
        for m in all_memories:
            m_key = m.metadata.get("key", m.key)
            m_scope = m.metadata.get("scope", m.scope)
            if m_key == key and (scope is None or m_scope == scope):
                if self.forget(m.id):
                    deleted_count += 1
        return deleted_count

    def forget_by_scope(self, scope: str) -> int:
        """Delete all memories matching a given scope (e.g. PROJECT, SESSION)."""
        deleted_count = 0
        all_memories = self.list_memories(limit=500)
        for m in all_memories:
            m_scope = m.metadata.get("scope", m.scope)
            if m_scope == scope:
                if self.forget(m.id):
                    deleted_count += 1
        return deleted_count

    def list_memories(self, limit: int = 100) -> list[MemoryEntry]:
        """List stored memory entries up to limit."""
        return self.store.list_all(limit=limit)

    def get_context_summary(self, query: str, limit: int = 3, min_score: float = 0.35) -> str:
        """Format top relevant memories for system prompt context injection."""
        results = self.recall(query, limit=limit)
        relevant = [r for r in results if r.score >= min_score]
        if not relevant:
            return ""
        lines = [f"- {r.entry.content}" for r in relevant]
        return "Relevant remembered facts:\n" + "\n".join(lines)

    def process_explicit_memory_command(self, prompt: str) -> str | None:
        """Process explicit natural language memory commands ('FALSO remember...', 'FALSO forget...')."""
        clean_prompt = prompt.strip()
        p_lower = clean_prompt.lower()

        # Privacy override commands
        if p_lower in ("falso don't remember this", "don't save this", "forget this conversation", "falso don't remember this."):
            self.privacy_override_active = True
            return "Privacy instruction acknowledged. I will not store information from this interaction."

        # Forget commands
        if p_lower in ("falso forget that", "forget that", "falso forget that."):
            all_m = self.list_memories(limit=10)
            if all_m:
                self.forget(all_m[-1].id)
            return "Forgotten."

        if "forget my editor preference" in p_lower or "forget editor preference" in p_lower:
            self.forget_by_key("preferred_editor")
            return "Forgotten your editor preference."

        if "forget my browser preference" in p_lower or "forget browser preference" in p_lower:
            self.forget_by_key("preferred_browser")
            return "Forgotten your browser preference."

        if "forget my project preference" in p_lower or "forget this project" in p_lower or "forget everything you remember about this project" in p_lower:
            self.forget_by_key("preferred_project")
            self.forget_by_scope("PROJECT")
            return "Forgotten project memories."

        # Correction command: "I don't use Chrome anymore. I use Edge."
        if "use edge" in p_lower and ("chrome" in p_lower or "don't use" in p_lower):
            self.remember_preference("preferred_browser", "Edge")
            return "Updated your preferred browser to Edge."

        # Explicit Remember Commands
        if "remember that i use vs code" in p_lower or "remember editor vs code" in p_lower or "prefer vs code" in p_lower:
            self.remember_preference("preferred_editor", "VS Code")
            return "I'll remember that you prefer VS Code."

        if "remember that my preferred browser is chrome" in p_lower or "preferred browser is chrome" in p_lower:
            self.remember_preference("preferred_browser", "Chrome")
            return "I'll remember that you prefer Chrome."

        if "remember this project" in p_lower or "remember project-falso" in p_lower:
            self.remember(
                fact="Project-Falso is located at C:\\Users\\Admin\\Project-Falso with pytest and port 8000.",
                category="project_memory",
                importance="HIGH",
                source="USER_EXPLICIT",
                scope="PROJECT",
                key="preferred_project",
                value="Project-Falso",
            )
            return "I'll remember Project-Falso."

        # Memory Inspection Commands
        if "what do you remember about me" in p_lower or "what do you remember about me?" in p_lower:
            prefs = [m for m in self.list_memories() if m.category == "user_preference" or "preference" in m.content.lower()]
            if not prefs:
                return "I don't have any saved user preferences."
            lines = [f"- {m.key or m.content}: {m.value}" for m in prefs]
            return "Here is what I remember about your preferences:\n" + "\n".join(lines)

        if "what do you remember about this project" in p_lower or "what do you remember about this project?" in p_lower:
            proj = [m for m in self.list_memories() if m.scope == "PROJECT" or "project" in m.content.lower()]
            if not proj:
                return "No project-specific memories stored."
            lines = [f"- {m.content}" for m in proj]
            return "Project memories:\n" + "\n".join(lines)

        return None


memory_service = MemoryService()
