"""
Trending Heap
=============
Maintains a real-time top-K trending usernames using a min-heap
(Python's heapq is a min-heap; we negate frequencies to simulate max-heap).

Also includes a HashMap (dict) for O(1) frequency lookups.

Complexity:
  Record search : O(log K)
  Top-K query   : O(K log K)
  Frequency get : O(1)
"""

from __future__ import annotations
import heapq
import threading
from collections import defaultdict
from typing import Optional


class TrendingHeap:
    """
    Tracks username search frequencies and exposes a top-K leaderboard.

    Internally uses:
      - A HashMap  (dict)   → O(1) frequency look-up
      - A Min-Heap           → O(log K) bounded top-K maintenance
    """

    def __init__(self, top_k: int = 20):
        self._top_k = top_k
        self._freq: dict[str, int] = defaultdict(int)   # HashMap
        self._heap: list[tuple[int, str]] = []           # (freq, username)
        self._in_heap: set[str] = set()
        self._lock = threading.Lock()

    def record(self, username: str, count: int = 1) -> None:
        """
        Increment the search count for `username` and update the top-K heap.

        HashMap update : O(1)
        Heap update    : O(log K)
        """
        username = username.lower().strip()
        if not username:
            return
        with self._lock:
            self._freq[username] += count
            self._update_heap(username)

    def _update_heap(self, username: str) -> None:
        freq = self._freq[username]
        if username in self._in_heap:
            # Re-build heap lazily on next top_k call (acceptable for our scale)
            return
        if len(self._heap) < self._top_k:
            heapq.heappush(self._heap, (freq, username))
            self._in_heap.add(username)
        elif freq > self._heap[0][0]:
            # Evict the lowest-frequency item
            _, evicted = heapq.heapreplace(self._heap, (freq, username))
            self._in_heap.discard(evicted)
            self._in_heap.add(username)

    def top_k(self, k: Optional[int] = None) -> list[dict]:
        """
        Return the top-K trending usernames sorted by frequency desc.

        Returns: [{"username": str, "count": int}, ...]
        """
        limit = k or self._top_k
        with self._lock:
            # Rebuild snapshot with current frequencies
            snapshot = [(self._freq[u], u) for _, u in self._heap]
            snapshot.sort(key=lambda x: -x[0])
            return [
                {"username": username, "count": freq}
                for freq, username in snapshot[:limit]
            ]

    def frequency(self, username: str) -> int:
        """O(1) frequency look-up via HashMap."""
        return self._freq.get(username.lower(), 0)

    def reset(self, username: str) -> None:
        with self._lock:
            self._freq.pop(username.lower(), None)

    def __len__(self) -> int:
        return len(self._freq)
