from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel
from typing import Optional

from app.services.search_service import search_service
from app.services.platform_checker import platform_checker

router = APIRouter()


class SearchResponse(BaseModel):
    query: str
    corrected_query: Optional[str]
    duration_ms: float
    results: list[dict]
    trending: list[dict]
    cache_hit: bool = False


class PlatformCheckResponse(BaseModel):
    username: str
    summary: dict
    platforms: list[dict]
    duration_ms: float


@router.get("", response_model=SearchResponse)
async def search(
    q: str = Query(..., min_length=1, max_length=100, description="Search query"),
    semantic: bool = Query(True, description="Include semantic search"),
    top_k: int = Query(20, ge=1, le=100),
):
    """
    Full-text brand search with BM25 + optional semantic ranking.

    Features:
    - BK-Tree typo correction ("did you mean?")
    - Elasticsearch BM25 relevance ranking
    - FAISS semantic similarity
    - Redis caching (sub-millisecond for cache hits)
    - Trending injection
    """
    if not q.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")
    return await search_service.search(q, include_semantic=semantic, top_k=top_k)


@router.get("/platforms/{username}", response_model=PlatformCheckResponse)
async def check_platforms(
    username: str,
    categories: Optional[str] = Query(None, description="Comma-separated categories: social,dev,gaming,creative"),
):
    """
    Concurrently check username availability across 50+ platforms.

    Uses asyncio + aiohttp with semaphore-bounded concurrency.
    All checks fire simultaneously — O(1) wall-clock time.
    Results are cached in Redis for 1 hour.
    """
    import time
    start = time.perf_counter()

    cats = categories.split(",") if categories else None
    results = await platform_checker.check(username, categories=cats)
    summary = platform_checker.availability_summary(results)

    return {
        "username": username,
        "summary": summary,
        "platforms": [
            {
                "platform": r.platform,
                "icon": r.icon,
                "category": r.category,
                "url": r.url,
                "available": r.available,
                "status_code": r.status_code,
                "error": r.error,
            }
            for r in results
        ],
        "duration_ms": round((time.perf_counter() - start) * 1000, 2),
    }
