from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.services.search_service import trie, bk_tree
from app.core.redis_client import get_redis
from app.core.config import settings
import json

router = APIRouter()


class AutocompleteResponse(BaseModel):
    prefix: str
    suggestions: list[dict]
    correction: str | None
    source: str   # "cache" | "trie"


@router.get("", response_model=AutocompleteResponse)
async def autocomplete(
    q: str = Query(..., min_length=1, max_length=50),
    limit: int = Query(10, ge=1, le=20),
):
    """
    Google-style autocomplete using Trie prefix search.

    - O(k) traversal where k = query length
    - Suggestions ranked by historical search frequency
    - Also returns BK-Tree typo correction if prefix not found in Trie
    - Results cached in Redis (5-minute TTL)
    """
    prefix = q.lower().strip()
    redis = get_redis()
    cache_key = f"autocomplete:{prefix}:{limit}"

    # Cache check
    cached = await redis.get(cache_key)
    if cached:
        data = json.loads(cached)
        data["source"] = "cache"
        return data

    # Trie search
    suggestions = trie.autocomplete(prefix, limit=limit)

    # BK-Tree correction if no suggestions
    correction = None
    if not suggestions:
        correction = bk_tree.correct(prefix, tolerance=2)
        if correction:
            suggestions = trie.autocomplete(correction, limit=limit)

    result = {
        "prefix": prefix,
        "suggestions": suggestions,
        "correction": correction,
        "source": "trie",
    }

    await redis.set(cache_key, json.dumps(result), ex=settings.CACHE_TTL_AUTOCOMPLETE)
    return result


@router.post("/seed")
async def seed_trie(words: list[str]):
    """Add words to the in-memory Trie (admin endpoint)."""
    trie.bulk_insert(words)
    for w in words:
        bk_tree.add(w)
    return {"inserted": len(words), "trie_size": len(trie)}
