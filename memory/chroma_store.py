from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from memory.base import BaseMemoryStore, MemoryEntry, MemorySearchResult

logger = logging.getLogger(__name__)


class ChromaMemoryStore(BaseMemoryStore):
    """Vector memory store backed by ChromaDB."""

    def __init__(self, persist_dir: Path | str | None = None) -> None:
        import chromadb  # type: ignore

        if persist_dir is None:
            from app.routes.conversations import CHATS_DIR
            persist_dir = CHATS_DIR / "vector_db"

        self.persist_dir = str(Path(persist_dir).resolve())
        self.client = chromadb.PersistentClient(path=self.persist_dir)
        self.collection = self.client.get_or_create_collection(name="falso_memories")

    def add(self, content: str, metadata: dict[str, Any] | None = None) -> MemoryEntry:
        entry = MemoryEntry(content=content.strip(), metadata=metadata or {})
        self.collection.add(
            documents=[entry.content],
            metadatas=[entry.metadata],
            ids=[entry.id],
        )
        return entry

    def search(self, query: str, limit: int = 5) -> list[MemorySearchResult]:
        res = self.collection.query(query_texts=[query], n_results=limit)
        results: list[MemorySearchResult] = []
        if not res or not res.get("documents") or not res["documents"][0]:
            return results

        docs = res["documents"][0]
        ids = res["ids"][0]
        metadatas = res.get("metadatas", [[]])[0]
        distances = res.get("distances", [[]])[0]

        for i in range(len(docs)):
            entry = MemoryEntry(
                id=ids[i],
                content=docs[i],
                metadata=metadatas[i] if i < len(metadatas) else {},
            )
            # Convert distance to similarity score
            dist = distances[i] if i < len(distances) else 1.0
            score = 1.0 / (1.0 + float(dist))
            results.append(MemorySearchResult(entry=entry, score=score))

        return results

    def delete(self, memory_id: str) -> bool:
        try:
            self.collection.delete(ids=[memory_id])
            return True
        except Exception:  # noqa: BLE001
            return False

    def update(
        self,
        memory_id: str,
        content: str | None = None,
        metadata: dict[str, Any] | None = None,
        importance: int | None = None,
        category: str | None = None,
    ) -> MemoryEntry | None:
        try:
            res = self.collection.get(ids=[memory_id])
            if not res or not res.get("documents"):
                return None
            old_doc = res["documents"][0]
            old_meta = (res.get("metadatas") or [{}])[0] or {}

            new_doc = content.strip() if content is not None else old_doc
            if metadata is not None:
                old_meta.update(metadata)
            if category is not None:
                old_meta["category"] = category
            if importance is not None:
                old_meta["importance"] = importance

            self.collection.update(ids=[memory_id], documents=[new_doc], metadatas=[old_meta])
            return MemoryEntry(id=memory_id, content=new_doc, metadata=old_meta)
        except Exception:  # noqa: BLE001
            return None

    def list_all(self, limit: int = 100) -> list[MemoryEntry]:
        get_res = self.collection.get(limit=limit)
        entries: list[MemoryEntry] = []
        if get_res and get_res.get("documents"):
            docs = get_res["documents"]
            ids = get_res["ids"]
            metas = get_res.get("metadatas") or []
            for i in range(len(docs)):
                entries.append(
                    MemoryEntry(
                        id=ids[i],
                        content=docs[i],
                        metadata=metas[i] if i < len(metas) else {},
                    )
                )
        return entries

    def clear(self) -> None:
        self.client.delete_collection(name="falso_memories")
        self.collection = self.client.get_or_create_collection(name="falso_memories")
