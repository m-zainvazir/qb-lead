"""Embeddings behind one interface (docs/decisions/0002-embeddings.md).

Callers ask `get_embedder()` for the configured provider and never import a provider
SDK themselves. Every vector is stored with `embedder.model` and `embedder.dims`.
"""

from __future__ import annotations

import hashlib
import math
import re
from functools import lru_cache
from typing import Any, Protocol

from core.settings import get_settings

DIMS = 384  # fixed by the vector(384) columns; see ADR 0002


class Embedder(Protocol):
    model: str
    dims: int

    def embed(self, texts: list[str]) -> list[list[float]]: ...


class FastEmbedEmbedder:
    """Local ONNX model via fastembed. Loaded lazily (the first call downloads it once)."""

    def __init__(self, model: str, cache_dir: str | None = None) -> None:
        self.model = model
        self.dims = DIMS
        self._cache_dir = cache_dir
        self._impl: Any = None

    def embed(self, texts: list[str]) -> list[list[float]]:
        if self._impl is None:
            from fastembed import TextEmbedding  # heavy import, worker only

            self._impl = TextEmbedding(model_name=self.model, cache_dir=self._cache_dir)
        vectors = [list(map(float, v)) for v in self._impl.embed(texts)]
        if vectors and len(vectors[0]) != self.dims:
            raise ValueError(f"{self.model} returned {len(vectors[0])} dims, expected {self.dims}")
        return vectors


class HashEmbedder:
    """Deterministic, dependency-free vectors for tests and offline runs. No semantics."""

    model = "hash-v1"
    dims = DIMS

    def embed(self, texts: list[str]) -> list[list[float]]:
        out = []
        for text in texts:
            vec = [0.0] * self.dims
            for token in re.findall(r"[a-z0-9]+", text.lower()):
                h = int.from_bytes(hashlib.sha256(token.encode()).digest()[:8], "big")
                vec[h % self.dims] += 1.0 if (h >> 63) & 1 else -1.0
            norm = math.sqrt(sum(v * v for v in vec)) or 1.0
            out.append([v / norm for v in vec])
        return out


@lru_cache(maxsize=1)
def get_embedder() -> Embedder:
    s = get_settings()
    if s.embedding_provider == "hash":
        return HashEmbedder()
    return FastEmbedEmbedder(s.embedding_model, s.embedding_cache_dir)


def to_pgvector(vector: list[float]) -> str:
    """pgvector's text format; passed as a parameter and cast in SQL (`%s::extensions.vector`)."""
    return "[" + ",".join(f"{v:.7f}" for v in vector) + "]"
