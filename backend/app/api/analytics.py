from fastapi import APIRouter, Query
from app.services.search_service import heap, trie, inv_idx

router = APIRouter()


@router.get("/trending")
async def trending(k: int = Query(20, ge=1, le=100)):
    """Top-K trending usernames from the in-memory max-heap."""
    return {"trending": heap.top_k(k=k), "heap_size": len(heap)}


@router.get("/trie/stats")
async def trie_stats():
    """Trie statistics."""
    return {"words": len(trie), "data_structure": "Trie (prefix tree)"}


@router.get("/index/stats")
async def index_stats():
    """Inverted index statistics."""
    return inv_idx.stats()


@router.get("/search")
async def inverted_index_search(
    q: str = Query(..., min_length=1),
    phrase: bool = Query(False),
):
    """
    Search the in-memory BM25 inverted index.
    Demonstrates the raw ranking engine without Elasticsearch.
    """
    if phrase:
        results = inv_idx.phrase_search(q)
    else:
        results = inv_idx.search(q)
    return {"query": q, "results": results, "engine": "in-memory BM25 inverted index"}
