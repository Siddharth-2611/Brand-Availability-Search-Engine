"""
BK-Tree (Burkhard-Keller Tree)
==============================
A metric tree for approximate string matching (typo correction).

Every node stores a word and edges are labelled with Levenshtein distances
to children. At query time we exploit the triangle inequality to prune entire
subtrees, making search sub-linear in practice.

Structure example (Levenshtein):
    "book"
     ├─1─ "books"
     ├─2─ "cook"
     │     └─2─ "cool"
     └─3─ "cape"

Query "boo", tolerance=1  →  ["book", "books"]

Time complexity:
  Build  : O(n log n) average, O(n²) worst
  Query  : O(n^0.3) average (highly query-dependent)
  Space  : O(n)
"""

from __future__ import annotations
from typing import Optional, Callable


def _levenshtein(s: str, t: str) -> int:
    """
    Pure-Python Levenshtein distance (Wagner-Fischer DP).
    Space: O(min(|s|,|t|))  Time: O(|s|×|t|)

    In production, swap for `python-Levenshtein` (C extension, ~100× faster):
        pip install python-Levenshtein
        import Levenshtein; _default_dist = Levenshtein.distance
    """
    if len(s) < len(t):
        s, t = t, s
    prev = list(range(len(t) + 1))
    for i, sc in enumerate(s, 1):
        curr = [i]
        for j, tc in enumerate(t, 1):
            curr.append(min(
                prev[j] + 1,        # deletion
                curr[j - 1] + 1,    # insertion
                prev[j - 1] + (sc != tc),  # substitution
            ))
        prev = curr
    return prev[-1]


# Default distance function: standard Levenshtein edit distance
_default_dist: Callable[[str, str], int] = _levenshtein


class BKNode:
    __slots__ = ("word", "children")

    def __init__(self, word: str):
        self.word: str = word
        self.children: dict[int, "BKNode"] = {}


class BKTree:
    """
    BK-Tree for approximate string matching.

    Example
    -------
    >>> tree = BKTree()
    >>> tree.bulk_add(["python", "cython", "pythan", "java", "javascript"])
    >>> tree.search("pythn", tolerance=2)
    [{'word': 'python', 'distance': 1}, {'word': 'pythan', 'distance': 2}]
    """

    def __init__(self, distance_fn: Callable[[str, str], int] = _default_dist):
        self.root: Optional[BKNode] = None
        self._dist = distance_fn
        self._size = 0

    # ── Mutation ──────────────────────────────────────────────────────

    def add(self, word: str) -> None:
        """Insert a word into the tree (O(log n) average)."""
        word = word.lower().strip()
        if not word:
            return
        if self.root is None:
            self.root = BKNode(word)
            self._size += 1
            return
        node = self.root
        while True:
            d = self._dist(word, node.word)
            if d == 0:
                return    # duplicate
            if d not in node.children:
                node.children[d] = BKNode(word)
                self._size += 1
                return
            node = node.children[d]

    def bulk_add(self, words: list[str]) -> None:
        for w in words:
            self.add(w)

    # ── Query ─────────────────────────────────────────────────────────

    def search(self, query: str, tolerance: int = 2) -> list[dict]:
        """
        Return all words within `tolerance` edits of `query`,
        sorted by ascending distance.

        Returns: [{"word": str, "distance": int}, ...]
        """
        query = query.lower().strip()
        if self.root is None:
            return []

        results: list[tuple[int, str]] = []
        stack = [self.root]

        while stack:
            node = stack.pop()
            d = self._dist(query, node.word)
            if d <= tolerance:
                results.append((d, node.word))
            # Triangle inequality pruning:
            # any child at edge-label e can only contain words in range
            # [d - tolerance, d + tolerance]
            lo, hi = d - tolerance, d + tolerance
            for edge, child in node.children.items():
                if lo <= edge <= hi:
                    stack.append(child)

        results.sort(key=lambda x: (x[0], x[1]))
        return [{"word": word, "distance": dist} for dist, word in results]

    def correct(self, query: str, tolerance: int = 2) -> Optional[str]:
        """Return the single closest match, or None if query is already correct."""
        if self.root is None:
            return None
        matches = self.search(query, tolerance)
        if not matches:
            return None
        best = matches[0]
        return best["word"] if best["distance"] > 0 else None

    # ── Info ──────────────────────────────────────────────────────────

    @property
    def size(self) -> int:
        return self._size

    def __len__(self) -> int:
        return self._size
