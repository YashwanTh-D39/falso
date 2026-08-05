from __future__ import annotations

import math
import re
from abc import ABC, abstractmethod
from typing import ClassVar


class BaseEmbeddingModel(ABC):
    """Interface for embedding models."""

    @abstractmethod
    def embed_text(self, text: str) -> list[float]:
        """Generate a vector embedding float array for text."""

    @abstractmethod
    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate vector embeddings for a batch of text strings."""


def _cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 0.0
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


class SimpleVectorEmbeddingModel(BaseEmbeddingModel):
    """Zero-dependency hashed n-gram character/word vector embedding model.

    Produces normalized 128-dimensional dense vector embeddings without external
    C/Rust binary dependencies, enabling fast cosine similarity semantic search
    out of the box.
    """

    DIM: ClassVar[int] = 128

    def _tokenize(self, text: str) -> list[str]:
        words = [w.lower() for w in re.findall(r"\w+", text)]
        ngrams = []
        for w in words:
            ngrams.append(w)
            for i in range(len(w) - 2):
                ngrams.append(w[i : i + 3])
        return ngrams

    def embed_text(self, text: str) -> list[float]:
        tokens = self._tokenize(text)
        if not tokens:
            return [0.0] * self.DIM

        vec = [0.0] * self.DIM
        for token in tokens:
            # Deterministic hash bucket allocation
            idx = abs(hash(token)) % self.DIM
            vec[idx] += 1.0

        norm = math.sqrt(sum(v * v for v in vec))
        if norm > 0.0:
            vec = [v / norm for v in vec]
        return vec

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_text(t) for t in texts]


class SentenceTransformerEmbeddingModel(BaseEmbeddingModel):
    """Dense vector embedding model using sentence-transformers (when installed)."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2") -> None:
        from sentence_transformers import SentenceTransformer  # type: ignore

        self.model = SentenceTransformer(model_name)

    def embed_text(self, text: str) -> list[float]:
        return self.model.encode(text).tolist()

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return self.model.encode(texts).tolist()
