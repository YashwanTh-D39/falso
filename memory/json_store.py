from __future__ import annotations

import json
import math
import re
import threading
from collections import Counter
from pathlib import Path
from typing import Any

from memory.base import BaseMemoryStore, MemoryEntry, MemorySearchResult


def _tokenize(text: str) -> list[str]:
    return [w.lower() for w in re.findall(r"\w+", text) if len(w) > 1]


def _compute_tf(tokens: list[str]) -> dict[str, float]:
    total = len(tokens)
    if total == 0:
        return {}
    counts = Counter(tokens)
    return {word: count / total for word, count in counts.items()}


class JSONMemoryStore(BaseMemoryStore):
    """File-backed JSON memory store with lightweight TF-IDF search.
    Requires no external dependencies.
    """

    def __init__(self, file_path: Path | str | None = None) -> None:
        if file_path is None:
            from app.routes.conversations import CHATS_DIR
            file_path = CHATS_DIR / "memories.json"
        self.file_path = Path(file_path)
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._memories: dict[str, MemoryEntry] = {}
        self._doc_tokens: dict[str, list[str]] = {}
        self._load()

    def _load(self) -> None:
        if not self.file_path.exists():
            return
        try:
            raw = json.loads(self.file_path.read_text(encoding="utf-8"))
            for item in raw:
                entry = MemoryEntry(
                    id=item["id"],
                    content=item["content"],
                    metadata=item.get("metadata", {}),
                    created_at=item.get("created_at", ""),
                )
                self._memories[entry.id] = entry
                self._doc_tokens[entry.id] = _tokenize(entry.content)
        except Exception:  # noqa: BLE001
            self._memories = {}
            self._doc_tokens = {}

    def _save(self) -> None:
        data = [
            {
                "id": m.id,
                "content": m.content,
                "metadata": m.metadata,
                "created_at": m.created_at,
            }
            for m in self._memories.values()
        ]
        tmp = self.file_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.file_path)

    def add(self, content: str, metadata: dict[str, Any] | None = None) -> MemoryEntry:
        entry = MemoryEntry(content=content.strip(), metadata=metadata or {})
        tokens = _tokenize(entry.content)
        with self._lock:
            self._memories[entry.id] = entry
            self._doc_tokens[entry.id] = tokens
            self._save()
        return entry

    def search(self, query: str, limit: int = 5) -> list[MemorySearchResult]:
        query_tokens = _tokenize(query)
        if not query_tokens or not self._memories:
            return []

        results: list[MemorySearchResult] = []
        with self._lock:
            memories = list(self._memories.values())

        # Document count
        n_docs = len(memories)
        doc_tokens_list = [self._doc_tokens.get(m.id, []) for m in memories]
        
        # Calculate IDF
        doc_freq: dict[str, int] = Counter()
        for doc_tokens in doc_tokens_list:
            unique_words = set(doc_tokens)
            for w in unique_words:
                doc_freq[w] += 1

        query_tf = _compute_tf(query_tokens)

        for i, entry in enumerate(memories):
            doc_tokens = doc_tokens_list[i]
            if not doc_tokens:
                continue
            doc_tf = _compute_tf(doc_tokens)
            
            # Dot product of query & document TF-IDF vectors
            score = 0.0
            for word, q_tf in query_tf.items():
                if word in doc_tf:
                    df = doc_freq.get(word, 1)
                    idf = math.log((n_docs + 1) / (df + 0.5)) + 1.0
                    score += q_tf * doc_tf[word] * (idf ** 2)

            if score > 0.0:
                results.append(MemorySearchResult(entry=entry, score=score))

        results.sort(key=lambda r: r.score, reverse=True)
        return results[:limit]

    def delete(self, memory_id: str) -> bool:
        with self._lock:
            if memory_id in self._memories:
                del self._memories[memory_id]
                self._doc_tokens.pop(memory_id, None)
                self._save()
                return True
            return False

    def list_all(self, limit: int = 100) -> list[MemoryEntry]:
        with self._lock:
            items = list(self._memories.values())
        return items[:limit]

    def clear(self) -> None:
        with self._lock:
            self._memories.clear()
            self._save()
