"""
Unit tests for all DSA implementations.
Run with: pytest tests/ -v
"""

import pytest
from app.algorithms.trie import Trie
from app.algorithms.bk_tree import BKTree
from app.algorithms.trending_heap import TrendingHeap
from app.algorithms.inverted_index import InvertedIndex


# ─── Trie Tests ───────────────────────────────────────────────────────────────

class TestTrie:

    def test_insert_and_search(self):
        t = Trie()
        t.insert("bytebot")
        assert t.search("bytebot") is True
        assert t.search("byte") is False

    def test_starts_with(self):
        t = Trie()
        t.insert("bytebot")
        assert t.starts_with("byte") is True
        assert t.starts_with("xyz") is False

    def test_autocomplete_returns_sorted_by_frequency(self):
        t = Trie()
        t.insert("bytebot",   frequency=100)
        t.insert("bytecoder", frequency=500)
        t.insert("byteforge", frequency=200)
        results = t.autocomplete("byte")
        assert results[0]["word"] == "bytecoder"   # highest freq first
        assert results[1]["word"] == "byteforge"

    def test_autocomplete_limit(self):
        t = Trie()
        for i in range(20):
            t.insert(f"test{i}")
        results = t.autocomplete("test", limit=5)
        assert len(results) == 5

    def test_delete(self):
        t = Trie()
        t.insert("hello")
        t.insert("hell")
        assert t.delete("hello") is True
        assert t.search("hello") is False
        assert t.search("hell") is True   # prefix still intact

    def test_bulk_insert(self):
        t = Trie()
        t.bulk_insert([("alpha", 10), ("beta", 20), "gamma"])
        assert len(t) == 3

    def test_increment_frequency(self):
        t = Trie()
        t.insert("hello", frequency=1)
        t.increment("hello")
        suggestions = t.autocomplete("hel")
        assert suggestions[0]["frequency"] == 2

    def test_empty_prefix_safe(self):
        t = Trie()
        t.insert("test")
        results = t.autocomplete("")
        assert isinstance(results, list)

    def test_contains_operator(self):
        t = Trie()
        t.insert("brand")
        assert "brand" in t
        assert "other" not in t


# ─── BK-Tree Tests ────────────────────────────────────────────────────────────

class TestBKTree:

    def test_exact_search(self):
        tree = BKTree()
        tree.add("python")
        results = tree.search("python", tolerance=0)
        assert len(results) == 1
        assert results[0]["distance"] == 0

    def test_typo_correction(self):
        tree = BKTree()
        tree.bulk_add(["python", "cython", "java", "javascript"])
        result = tree.correct("pythn", tolerance=2)
        assert result == "python"   # unambiguous closest match

    def test_no_correction_for_exact_match(self):
        tree = BKTree()
        tree.add("python")
        assert tree.correct("python") is None

    def test_tolerance_filtering(self):
        tree = BKTree()
        tree.bulk_add(["book", "books", "cook", "look", "cape"])
        results_1 = tree.search("boo", tolerance=1)
        results_2 = tree.search("boo", tolerance=2)
        assert len(results_2) >= len(results_1)

    def test_results_sorted_by_distance(self):
        tree = BKTree()
        tree.bulk_add(["book", "boot", "cook"])
        results = tree.search("book", tolerance=2)
        distances = [r["distance"] for r in results]
        assert distances == sorted(distances)

    def test_empty_tree(self):
        tree = BKTree()
        assert tree.search("anything") == []
        assert tree.correct("anything") is None

    def test_duplicate_ignored(self):
        tree = BKTree()
        tree.add("word")
        tree.add("word")
        assert len(tree) == 1


# ─── TrendingHeap Tests ───────────────────────────────────────────────────────

class TestTrendingHeap:

    def test_top_k_ordering(self):
        h = TrendingHeap(top_k=10)
        h.record("bytebot", 1200)
        h.record("devguru", 1000)
        h.record("agentai", 900)
        top = h.top_k(k=3)
        assert top[0]["username"] == "bytebot"
        assert top[0]["count"] == 1200

    def test_frequency_lookup(self):
        h = TrendingHeap()
        h.record("alpha", 5)
        h.record("alpha", 3)
        assert h.frequency("alpha") == 8

    def test_top_k_limit(self):
        h = TrendingHeap(top_k=5)
        for i in range(10):
            h.record(f"user{i}", i * 10)
        top = h.top_k(k=5)
        assert len(top) <= 5

    def test_unknown_username_frequency_zero(self):
        h = TrendingHeap()
        assert h.frequency("nobody") == 0

    def test_reset(self):
        h = TrendingHeap()
        h.record("test", 10)
        h.reset("test")
        assert h.frequency("test") == 0


# ─── InvertedIndex / BM25 Tests ───────────────────────────────────────────────

class TestInvertedIndex:

    def _make_index(self):
        idx = InvertedIndex()
        idx.add_document("doc1", "byte forge brand identity", {"title": "ByteForge"})
        idx.add_document("doc2", "byte coder python developer", {"title": "ByteCoder"})
        idx.add_document("doc3", "ai agent flow machine learning", {"title": "AgentFlow"})
        return idx

    def test_basic_search(self):
        idx = self._make_index()
        results = idx.search("byte")
        assert len(results) >= 2
        ids = [r["doc_id"] for r in results]
        assert "doc1" in ids
        assert "doc2" in ids

    def test_bm25_higher_score_for_more_occurrences(self):
        idx = InvertedIndex()
        idx.add_document("rich", "python python python developer")
        idx.add_document("sparse", "python developer java")
        results = idx.search("python")
        assert results[0]["doc_id"] == "rich"

    def test_phrase_search(self):
        idx = self._make_index()
        results = idx.phrase_search("byte forge")
        assert any(r["doc_id"] == "doc1" for r in results)
        assert all(r["doc_id"] != "doc2" for r in results)

    def test_remove_document(self):
        idx = self._make_index()
        idx.remove_document("doc1")
        results = idx.search("forge")
        assert all(r["doc_id"] != "doc1" for r in results)

    def test_stats(self):
        idx = self._make_index()
        stats = idx.stats()
        assert stats["documents"] == 3
        assert stats["unique_terms"] > 0

    def test_empty_query(self):
        idx = self._make_index()
        assert idx.search("") == []

    def test_missing_term(self):
        idx = self._make_index()
        results = idx.search("xyznotexist")
        assert results == []
