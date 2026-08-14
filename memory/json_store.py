from __future__ import annotations

import json
import math
import re
import threading
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from memory.base import BaseMemoryStore, MemoryEntry, MemorySearchResult
from memory.embeddings import SimpleVectorEmbeddingModel, _cosine_similarity


def _tokenize(text: str) -> list[str]:
    return [w.lower() for w in re.findall(r"\w+", text) if len(w) > 1]


def _compute_tf(tokens: list[str]) -> dict[str, float]:
    total = len(tokens)
    if total == 0:
        return {}
    counts = Counter(tokens)
    return {word: count / total for word, count in counts.items()}


class JSONMemoryStore(BaseMemoryStore):
    """File-backed JSON memory store with hybrid semantic vector + TF-IDF search.
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
        self._embeddings: dict[str, list[float]] = {}
        self.embedder = SimpleVectorEmbeddingModel()
        self._load()

    def _load(self) -> None:
        if not self.file_path.exists():
            return
        try:
            raw = json.loads(self.file_path.read_text(encoding="utf-8"))
            for item in raw:
                meta = item.get("metadata", {})
                entry = MemoryEntry(
                    id=item["id"],
                    content=item["content"],
                    category=item.get("category") or meta.get("category", "general"),
                    importance=item.get("importance") or meta.get("importance", 1),
                    source=item.get("source") or meta.get("source", "user_explicit"),
                    metadata=meta,
                    created_at=item.get("created_at", ""),
                    updated_at=item.get("updated_at") or item.get("created_at", ""),
                )
                self._memories[entry.id] = entry
                self._doc_tokens[entry.id] = _tokenize(entry.content)
                self._embeddings[entry.id] = self.embedder.embed_text(entry.content)
        except Exception:  # noqa: BLE001
            self._memories = {}
            self._doc_tokens = {}
            self._embeddings = {}

    def _save(self) -> None:
        data = [
            {
                "id": m.id,
                "content": m.content,
                "category": m.category,
                "importance": m.importance,
                "source": m.source,
                "metadata": m.metadata,
                "created_at": m.created_at,
                "updated_at": m.updated_at,
            }
            for m in self._memories.values()
        ]
        tmp = self.file_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        for attempt in range(5):
            try:
                tmp.replace(self.file_path)
                break
            except OSError:
                if attempt == 4:
                    raise
                time.sleep(0.05)

    def add(self, content: str, metadata: dict[str, Any] | None = None) -> MemoryEntry:
        cleaned_content = content.strip()
        meta = metadata or {}
        cat = meta.get("category", "general")
        imp = meta.get("importance", 1)
        src = meta.get("source", "user_explicit")

        # Duplicate detection: check if exact or normalized content exists
        norm_target = cleaned_content.lower()
        with self._lock:
            for existing_id, existing_entry in self._memories.items():
                if existing_entry.content.strip().lower() == norm_target:
                    # Duplicate found — update existing entry instead of adding a duplicate
                    existing_entry.updated_at = datetime.now(UTC).isoformat()
                    existing_entry.metadata["updated_at"] = existing_entry.updated_at
                    if meta:
                        existing_entry.metadata.update(meta)
                    if cat != "general":
                        existing_entry.category = cat
                    if imp > existing_entry.importance:
                        existing_entry.importance = imp
                    self._save()
                    return existing_entry

        entry = MemoryEntry(
            content=cleaned_content,
            category=cat,
            importance=imp,
            source=src,
            metadata=meta,
        )
        tokens = _tokenize(entry.content)
        embedding = self.embedder.embed_text(entry.content)
        with self._lock:
            self._memories[entry.id] = entry
            self._doc_tokens[entry.id] = tokens
            self._embeddings[entry.id] = embedding
            self._save()
        return entry

    def update(
        self,
        memory_id: str,
        content: str | None = None,
        metadata: dict[str, Any] | None = None,
        importance: int | None = None,
        category: str | None = None,
    ) -> MemoryEntry | None:
        with self._lock:
            entry = self._memories.get(memory_id)
            if entry is None:
                return None

            if content is not None:
                entry.content = content.strip()
                self._doc_tokens[entry.id] = _tokenize(entry.content)
                self._embeddings[entry.id] = self.embedder.embed_text(entry.content)

            if category is not None:
                entry.category = category
                entry.metadata["category"] = category

            if importance is not None:
                entry.importance = importance
                entry.metadata["importance"] = importance

            if metadata is not None:
                entry.metadata.update(metadata)

            entry.updated_at = datetime.now(UTC).isoformat()
            entry.metadata["updated_at"] = entry.updated_at
            self._save()
            return entry

    def search(self, query: str, limit: int = 5) -> list[MemorySearchResult]:
        query_tokens = _tokenize(query)
        if not query_tokens or not self._memories:
            return []

        query_vector = self.embedder.embed_text(query)
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
            doc_emb = self._embeddings.get(entry.id, [])
            
            # Hybrid scoring: TF-IDF + Cosine Similarity
            vector_sim = _cosine_similarity(query_vector, doc_emb) if doc_emb else 0.0
            
            tfidf_score = 0.0
            if doc_tokens:
                doc_tf = _compute_tf(doc_tokens)
                for word, q_tf in query_tf.items():
                    if word in doc_tf:
                        df = doc_freq.get(word, 1)
                        idf = math.log((n_docs + 1) / (df + 0.5)) + 1.0
                        tfidf_score += q_tf * doc_tf[word] * (idf ** 2)

            if tfidf_score > 0:
                total_score = tfidf_score + (vector_sim * 1.5)
            else:
                total_score = vector_sim * 0.25

            if total_score > 0.05:
                results.append(MemorySearchResult(entry=entry, score=total_score))

        results.sort(key=lambda r: r.score, reverse=True)
        return results[:limit]

    def delete(self, memory_id: str) -> bool:
        with self._lock:
            if memory_id in self._memories:
                del self._memories[memory_id]
                self._doc_tokens.pop(memory_id, None)
                self._embeddings.pop(memory_id, None)
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
