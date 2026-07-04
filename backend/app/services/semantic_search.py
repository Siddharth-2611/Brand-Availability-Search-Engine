"""
Semantic Search Service
========================
Uses sentence-transformers to embed queries and usernames into
384-dimensional vectors, then FAISS for sub-millisecond ANN search.

Example:
  Query: "ai startup"
  Results: ["agentforge", "aibuilder", "smartagent"]  — even though
  none of these contain "ai startup" as a substring.
"""

from __future__ import annotations
import asyncio
import os
import pickle
import threading
from typing import Optional

import numpy as np

from app.core.config import settings

try:
    from sentence_transformers import SentenceTransformer
    import faiss
    _AVAILABLE = True
except ImportError:
    _AVAILABLE = False
    print("⚠️  sentence-transformers / faiss not installed — semantic search disabled")


class SemanticSearchService:
    """Wraps FAISS + SentenceTransformer for semantic username search."""

    def __init__(self):
        self._model: Optional["SentenceTransformer"] = None
        self._index: Optional["faiss.IndexFlatIP"] = None
        self._id_map: list[str] = []        # FAISS row → username
        self._lock = threading.Lock()
        self._ready = False

    def load(self) -> None:
        if not _AVAILABLE:
            return
        self._model = SentenceTransformer(settings.EMBEDDING_MODEL)
        dim = self._model.get_sentence_embedding_dimension()

        # Inner-product index (cosine similarity after L2 normalisation)
        self._index = faiss.IndexFlatIP(dim)

        if os.path.exists(settings.FAISS_INDEX_PATH):
            self._load_from_disk()

        self._ready = True
        print(f"✅  FAISS index ready (dim={dim}, size={self._index.ntotal})")

    def _load_from_disk(self) -> None:
        meta_path = settings.FAISS_INDEX_PATH + ".meta"
        if os.path.exists(meta_path):
            self._index = faiss.read_index(settings.FAISS_INDEX_PATH)
            with open(meta_path, "rb") as f:
                self._id_map = pickle.load(f)

    def _save_to_disk(self) -> None:
        faiss.write_index(self._index, settings.FAISS_INDEX_PATH)
        with open(settings.FAISS_INDEX_PATH + ".meta", "wb") as f:
            pickle.dump(self._id_map, f)

    def _embed(self, texts: list[str]) -> np.ndarray:
        vecs = self._model.encode(texts, convert_to_numpy=True, normalize_embeddings=True)
        return vecs.astype(np.float32)

    # ── Public API ────────────────────────────────────────────────────

    def add_usernames(self, usernames: list[str]) -> None:
        if not self._ready:
            return
        with self._lock:
            vecs = self._embed(usernames)
            self._index.add(vecs)
            self._id_map.extend(usernames)
            self._save_to_disk()

    def search(self, query: str, top_k: int = 10) -> list[dict]:
        """
        Find semantically similar usernames.

        Returns: [{"username": str, "score": float}, ...]
        """
        if not self._ready or self._index.ntotal == 0:
            return []

        q_vec = self._embed([query])
        scores, indices = self._index.search(q_vec, min(top_k, self._index.ntotal))

        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx == -1:
                continue
            results.append({
                "username": self._id_map[idx],
                "score": float(round(score, 4)),
            })
        return results

    async def search_async(self, query: str, top_k: int = 10) -> list[dict]:
        """Non-blocking wrapper for use in FastAPI handlers."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.search, query, top_k)

    @property
    def is_ready(self) -> bool:
        return self._ready

    @property
    def index_size(self) -> int:
        if self._index is None:
            return 0
        return self._index.ntotal


# Module-level singleton
semantic_search = SemanticSearchService()
