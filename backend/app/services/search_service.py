"""
Search Service
==============
Orchestrates all search components:
  1. Trie      → autocomplete suggestions
  2. BK-Tree   → typo correction / "did you mean?"
  3. Elasticsearch → BM25 full-text ranking
  4. FAISS     → semantic similarity
  5. Redis     → result caching
  6. Heap      → trending injection
"""

from __future__ import annotations
import asyncio
import json
import time
from typing import Optional

from app.algorithms.trie import Trie
from app.algorithms.bk_tree import BKTree
from app.algorithms.trending_heap import TrendingHeap
from app.algorithms.inverted_index import InvertedIndex
from app.core.redis_client import get_redis
from app.core.elasticsearch_client import get_es
from app.core.config import settings


# ── Module-level in-memory structures ────────────────────────────────

trie    = Trie()
bk_tree = BKTree()
heap    = TrendingHeap(top_k=50)
inv_idx = InvertedIndex()

# Seed with common brand-name patterns for demo purposes.
# Every real search also gets added automatically (see SearchService.search),
# so this list only needs to cover the initial out-of-the-box experience.
_SEED_WORDS = [
    "bytebot", "bytecoder", "byteforge", "byteflow", "bytemind", "bytebytego",
    "devguru", "devforge", "devflow", "devlabs", "devhive",
    "agentforge", "agentai", "agentflow", "agentlabs",
    "aibuilder", "aiforge", "aiflow", "aimind",
    "smartagent", "smartbuild", "smartcode", "smartlabs",
    "techforge", "techflow", "techhive", "techwave",
    "cloudnova", "cloudforge", "cloudflow", "cloudmind",
    "datastream", "dataflow", "datahive", "dataforge",
    "pixelcraft", "pixelflow", "pixelforge",
    "nexusai", "nexusflow", "nexusforge",
    "codecraft", "codehive", "codenest", "buildstack",
    "launchpad", "launchbase", "foundrylabs", "sparkforge",
]

for w in _SEED_WORDS:
    trie.insert(w, frequency=100)
    bk_tree.add(w)


class SearchService:

    async def search(
        self,
        query: str,
        include_semantic: bool = True,
        top_k: int = 20,
    ) -> dict:
        """
        Full search pipeline.

        Returns:
          {
            "query": str,
            "corrected_query": str | None,
            "duration_ms": float,
            "results": [...],
            "trending": [...],
          }
        """
        start = time.perf_counter()
        query = query.strip().lower()

        redis = get_redis()

        # ── 1. Cache check ────────────────────────────────────────────
        cache_key = f"search:{query}"
        cached = await redis.get(cache_key)
        if cached:
            data = json.loads(cached)
            data["cache_hit"] = True
            return data

        # ── 2. Typo correction (BK-Tree) ──────────────────────────────
        corrected: Optional[str] = None
        active_query = query
        if not bk_tree.search(query, tolerance=0):   # exact not found
            suggestion = bk_tree.correct(query, tolerance=2)
            if suggestion:
                corrected = suggestion
                active_query = suggestion

        # ── 3. Elasticsearch BM25 ─────────────────────────────────────
        es_results = await self._es_search(active_query, top_k)

        # ── 4. Semantic search (FAISS) ────────────────────────────────
        semantic_results: list[dict] = []
        if include_semantic:
            try:
                from app.services.semantic_search import semantic_search
                if semantic_search.is_ready:
                    semantic_results = await semantic_search.search_async(active_query, top_k=10)
            except Exception:
                pass

        # ── 5. Merge & deduplicate ────────────────────────────────────
        results = self._merge_results(es_results, semantic_results)

        # ── 6. Update trending heap + Trie/BK-Tree (learn this query) ──
        heap.record(query)
        trie.insert(query)          # inserts if new, increments if existing
        bk_tree.add(query)          # add() is a no-op if already present

        # ── 7. Trending injection ─────────────────────────────────────
        trending = heap.top_k(k=10)

        duration_ms = (time.perf_counter() - start) * 1000

        payload = {
            "query": query,
            "corrected_query": corrected,
            "duration_ms": round(duration_ms, 2),
            "results": results[:top_k],
            "trending": trending,
            "cache_hit": False,
        }

        # Cache for 5 minutes
        await redis.set(cache_key, json.dumps(payload), ex=300)

        return payload

    async def _es_search(self, query: str, top_k: int) -> list[dict]:
        """BM25 search via Elasticsearch."""
        try:
            es = get_es()
            body = {
                "query": {
                    "multi_match": {
                        "query": query,
                        "fields": ["name^3", "description^1", "tags^2"],
                        "type": "best_fields",
                        "fuzziness": "AUTO",
                    }
                },
                "size": top_k,
                "highlight": {
                    "fields": {"name": {}, "description": {}},
                    "pre_tags": ["<mark>"],
                    "post_tags": ["</mark>"],
                },
            }
            resp = await es.search(index=settings.ES_INDEX_BRANDS, body=body)
            return [
                {
                    "id": hit["_id"],
                    "score": hit["_score"],
                    "source": "elasticsearch",
                    **hit["_source"],
                    "highlights": hit.get("highlight", {}),
                }
                for hit in resp["hits"]["hits"]
            ]
        except Exception:
            return []

    def _merge_results(
        self,
        bm25: list[dict],
        semantic: list[dict],
    ) -> list[dict]:
        """
        Reciprocal Rank Fusion (RRF) to merge BM25 and semantic results.
        score_rrf = Σ 1 / (k + rank_i),  k = 60 (standard constant)
        """
        K = 60
        fused: dict[str, float] = {}

        for rank, item in enumerate(bm25, start=1):
            key = item.get("name", item.get("doc_id", str(rank)))
            fused[key] = fused.get(key, 0) + 1 / (K + rank)

        for rank, item in enumerate(semantic, start=1):
            key = item.get("username", str(rank))
            fused[key] = fused.get(key, 0) + 1 / (K + rank)

        # Return BM25 hits re-ranked by RRF score
        bm25_by_name = {h.get("name", ""): h for h in bm25}
        ranked_keys = sorted(fused, key=lambda k: -fused[k])

        result = []
        seen: set[str] = set()
        for key in ranked_keys:
            if key in seen:
                continue
            seen.add(key)
            if key in bm25_by_name:
                item = bm25_by_name[key].copy()
                item["rrf_score"] = round(fused[key], 6)
                result.append(item)
            else:
                result.append({"name": key, "source": "semantic", "rrf_score": round(fused[key], 6)})
        return result


search_service = SearchService()
