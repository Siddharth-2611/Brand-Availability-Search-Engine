"""
Inverted Index with BM25 Ranking
=================================
An in-memory full-text search engine used alongside Elasticsearch.

Inverted index structure:
  {
    "byte": {doc1: [0, 4], doc7: [2]},   # term → {doc_id → positions}
    "forge": {doc1: [1], doc12: [0]},
  }

BM25 formula (Okapi BM25):
  score(q, d) = Σ IDF(t) × [TF(t,d) × (k1+1)] / [TF(t,d) + k1×(1-b+b×|d|/avgdl)]

  k1 = 1.5   (term-frequency saturation)
  b  = 0.75  (document-length normalisation)
"""

from __future__ import annotations
import math
import re
from collections import defaultdict
from typing import Any


def _tokenize(text: str) -> list[str]:
    """Lowercase alphanumeric tokenisation."""
    return re.findall(r"[a-z0-9]+", text.lower())


class InvertedIndex:
    """
    In-memory inverted index with BM25 scoring.

    index:
      term → {doc_id → [positions]}
    """

    K1 = 1.5
    B  = 0.75

    def __init__(self):
        # term  → {doc_id: [pos, ...]}
        self._index: dict[str, dict[str, list[int]]] = defaultdict(lambda: defaultdict(list))
        # doc_id → metadata (title, description, …)
        self._docs: dict[str, dict[str, Any]] = {}
        # doc_id → token count
        self._doc_len: dict[str, int] = {}
        self._total_tokens = 0

    # ── Indexing ─────────────────────────────────────────────────────

    def add_document(self, doc_id: str, text: str, metadata: dict | None = None) -> None:
        """
        Index a document.
        Insert: O(|tokens|)
        """
        tokens = _tokenize(text)
        self._docs[doc_id] = metadata or {}
        self._doc_len[doc_id] = len(tokens)
        self._total_tokens += len(tokens)

        for pos, token in enumerate(tokens):
            self._index[token][doc_id].append(pos)

    def remove_document(self, doc_id: str) -> None:
        if doc_id not in self._docs:
            return
        self._total_tokens -= self._doc_len.pop(doc_id, 0)
        del self._docs[doc_id]
        for term_docs in self._index.values():
            term_docs.pop(doc_id, None)

    # ── Search ────────────────────────────────────────────────────────

    def search(self, query: str, top_n: int = 10) -> list[dict]:
        """
        BM25-ranked search.  O(|query_terms| × |matching_docs|).

        Returns: [{"doc_id": str, "score": float, "metadata": dict}, ...]
        """
        query_terms = _tokenize(query)
        if not query_terms:
            return []

        n_docs  = len(self._docs)
        avg_dl  = self._total_tokens / max(n_docs, 1)
        scores: dict[str, float] = defaultdict(float)

        for term in query_terms:
            if term not in self._index:
                continue
            posting = self._index[term]
            df = len(posting)   # number of docs containing the term

            # IDF component (with smoothing to avoid division by zero)
            idf = math.log((n_docs - df + 0.5) / (df + 0.5) + 1)

            for doc_id, positions in posting.items():
                tf = len(positions)
                dl = self._doc_len[doc_id]
                # BM25 TF component
                tf_bm25 = (tf * (self.K1 + 1)) / (
                    tf + self.K1 * (1 - self.B + self.B * dl / avg_dl)
                )
                scores[doc_id] += idf * tf_bm25

        ranked = sorted(scores.items(), key=lambda x: -x[1])[:top_n]
        return [
            {"doc_id": doc_id, "score": round(score, 4), "metadata": self._docs.get(doc_id, {})}
            for doc_id, score in ranked
        ]

    def phrase_search(self, phrase: str, top_n: int = 10) -> list[dict]:
        """
        Exact phrase search using positional index.
        Returns docs where all tokens appear consecutively.
        O(|phrase_tokens| × |candidate_docs|)
        """
        tokens = _tokenize(phrase)
        if not tokens:
            return []

        # Candidate docs must contain every term
        candidate_ids: set[str] = set(self._index.get(tokens[0], {}).keys())
        for token in tokens[1:]:
            candidate_ids &= set(self._index.get(token, {}).keys())

        matched: list[str] = []
        for doc_id in candidate_ids:
            # Check for consecutive positions
            first_positions = self._index[tokens[0]][doc_id]
            for start_pos in first_positions:
                if all(
                    (start_pos + i) in self._index[tokens[i]][doc_id]
                    for i in range(1, len(tokens))
                ):
                    matched.append(doc_id)
                    break

        return [
            {"doc_id": doc_id, "score": 1.0, "metadata": self._docs.get(doc_id, {})}
            for doc_id in matched[:top_n]
        ]

    # ── Stats ─────────────────────────────────────────────────────────

    @property
    def doc_count(self) -> int:
        return len(self._docs)

    @property
    def term_count(self) -> int:
        return len(self._index)

    def stats(self) -> dict:
        return {
            "documents": self.doc_count,
            "unique_terms": self.term_count,
            "total_tokens": self._total_tokens,
            "avg_doc_length": round(self._total_tokens / max(self.doc_count, 1), 2),
        }
