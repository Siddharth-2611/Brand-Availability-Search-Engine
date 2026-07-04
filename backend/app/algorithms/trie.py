"""
Trie (Prefix Tree)
==================
Used for O(k) autocomplete suggestions where k = query length.

  b
  ├── y
  │   └── t
  │       └── e          <- "byte"
  │           ├── b
  │           │   └── o
  │           │       └── t  <- "bytebot"  ★
  │           └── f
  │               └── o
  │                   └── r
  │                       └── g
  │                           └── e  <- "byteforge"  ★

Insert  : O(n)   — n = word length
Search  : O(n)
Suggest : O(n + k) — k = number of suggestions collected
Space   : O(ALPHABET_SIZE × n × N)  — N = total words
"""

from __future__ import annotations
import threading
from typing import Optional


class TrieNode:
    __slots__ = ("children", "is_end", "frequency", "word")

    def __init__(self):
        self.children: dict[str, "TrieNode"] = {}
        self.is_end: bool = False
        self.frequency: int = 0   # how often this word was searched
        self.word: Optional[str] = None


class Trie:
    """Thread-safe Trie with frequency-ranked autocomplete."""

    def __init__(self):
        self.root = TrieNode()
        self._lock = threading.RLock()
        self._size = 0

    # ── Mutation ──────────────────────────────────────────────────────

    def insert(self, word: str, frequency: int = 1) -> None:
        """Insert a word (O(n))."""
        word = word.lower().strip()
        if not word:
            return
        with self._lock:
            node = self.root
            for ch in word:
                if ch not in node.children:
                    node.children[ch] = TrieNode()
                node = node.children[ch]
            if node.is_end:
                node.frequency += frequency          # bump existing
            else:
                node.is_end = True
                node.frequency = frequency
                node.word = word
                self._size += 1

    def increment(self, word: str) -> None:
        """Increment search frequency for an existing word."""
        word = word.lower().strip()
        with self._lock:
            node = self.root
            for ch in word:
                if ch not in node.children:
                    return       # word not in trie
                node = node.children[ch]
            if node.is_end:
                node.frequency += 1

    def delete(self, word: str) -> bool:
        """Delete a word; returns True if it was present and removed."""
        word = word.lower().strip()
        with self._lock:
            if not self.search(word):
                return False
            self._delete(self.root, word, 0)
            return True

    def _delete(self, node: TrieNode, word: str, depth: int) -> bool:
        """
        Recursively unmark/prune nodes for `word`.
        Return value signals to the PARENT call whether it's safe to prune
        the child edge just processed — it does not indicate overall
        deletion success (that's determined by the caller in delete()).
        """
        if depth == len(word):
            if not node.is_end:
                return False
            node.is_end = False
            node.word = None
            self._size -= 1
            return len(node.children) == 0   # safe to delete?
        ch = word[depth]
        if ch not in node.children:
            return False
        should_delete_child = self._delete(node.children[ch], word, depth + 1)
        if should_delete_child:
            del node.children[ch]
            return not node.is_end and len(node.children) == 0
        return False

    # ── Query ─────────────────────────────────────────────────────────

    def search(self, word: str) -> bool:
        """Exact match (O(n))."""
        node = self._traverse(word.lower().strip())
        return node is not None and node.is_end

    def starts_with(self, prefix: str) -> bool:
        """Prefix existence check (O(n))."""
        return self._traverse(prefix.lower().strip()) is not None

    def autocomplete(self, prefix: str, limit: int = 10) -> list[dict]:
        """
        Return up to `limit` completions for `prefix`,
        sorted by descending frequency.

        Returns: [{"word": str, "frequency": int}, ...]
        """
        prefix = prefix.lower().strip()
        node = self._traverse(prefix)
        if node is None:
            return []

        results: list[tuple[int, str]] = []
        self._dfs(node, results)

        # Sort by frequency desc, then lexicographically
        results.sort(key=lambda x: (-x[0], x[1]))
        return [
            {"word": word, "frequency": freq}
            for freq, word in results[:limit]
        ]

    # ── Helpers ───────────────────────────────────────────────────────

    def _traverse(self, prefix: str) -> Optional[TrieNode]:
        node = self.root
        for ch in prefix:
            if ch not in node.children:
                return None
            node = node.children[ch]
        return node

    def _dfs(
        self,
        node: TrieNode,
        results: list[tuple[int, str]],
        max_collect: int = 100,
    ) -> None:
        """DFS to collect all complete words under a node."""
        if len(results) >= max_collect:
            return
        if node.is_end and node.word:
            results.append((node.frequency, node.word))
        for child in node.children.values():
            self._dfs(child, results, max_collect)

    @property
    def size(self) -> int:
        return self._size

    def __len__(self) -> int:
        return self._size

    def __contains__(self, word: str) -> bool:
        return self.search(word)

    def bulk_insert(self, words: list[str | tuple]) -> None:
        """
        Insert many words at once.
        Accepts str or (word, frequency) tuples.
        """
        for item in words:
            if isinstance(item, tuple):
                self.insert(item[0], item[1])
            else:
                self.insert(item)
