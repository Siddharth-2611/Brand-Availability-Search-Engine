"""
Background Tasks
================
All tasks run in a separate Celery worker process,
communicating via RabbitMQ and storing results in Redis.
"""

import asyncio
import json
import logging
from datetime import datetime

from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=5)
def check_username_platforms_async(self, username: str, categories: list | None = None):
    """
    Trigger a full platform check for a username in the background.
    Result stored in Redis; frontend can poll /api/v1/search/platforms/{username}.
    """
    try:
        from app.services.platform_checker import platform_checker
        import redis as sync_redis
        from app.core.config import settings

        results = asyncio.run(platform_checker.check(username, categories=categories))
        summary = platform_checker.availability_summary(results)

        # Store completed result
        r = sync_redis.from_url(settings.REDIS_URL, decode_responses=True)
        key = f"task:platform:{username}"
        payload = {
            "status": "done",
            "username": username,
            "summary": summary,
            "results": [
                {
                    "platform": res.platform,
                    "icon": res.icon,
                    "available": res.available,
                    "url": res.url,
                }
                for res in results
            ],
            "completed_at": datetime.utcnow().isoformat(),
        }
        r.set(key, json.dumps(payload), ex=3600)
        return payload

    except Exception as exc:
        logger.exception(f"Platform check failed for {username}")
        raise self.retry(exc=exc)


@celery_app.task
def index_brand_in_elasticsearch(doc_id: str, name: str, description: str, tags: list):
    """Index a new brand entry into Elasticsearch."""
    from elasticsearch import Elasticsearch
    from app.core.config import settings

    es = Elasticsearch([settings.ELASTICSEARCH_URL])
    es.index(
        index=settings.ES_INDEX_BRANDS,
        id=doc_id,
        document={
            "name": name,
            "description": description,
            "tags": tags,
            "created_at": datetime.utcnow().isoformat(),
        },
    )
    logger.info(f"Indexed brand {doc_id} in Elasticsearch")
    return {"indexed": doc_id}


@celery_app.task
def snapshot_trending():
    """
    Periodic task: snapshot the in-memory trending heap to PostgreSQL
    so trending data survives worker restarts.
    """
    from app.services.search_service import heap
    import psycopg2
    from app.core.config import settings

    top = heap.top_k(k=100)
    if not top:
        return

    # Strip asyncpg prefix for sync psycopg2
    db_url = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")

    try:
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()
        for item in top:
            cur.execute(
                """
                INSERT INTO trending (username, search_count, last_searched)
                VALUES (%s, %s, NOW())
                ON CONFLICT (username) DO UPDATE
                  SET search_count = GREATEST(trending.search_count, EXCLUDED.search_count),
                      last_searched = NOW()
                """,
                (item["username"], item["count"]),
            )
        conn.commit()
        cur.close()
        conn.close()
        logger.info(f"Snapshotted {len(top)} trending usernames to PostgreSQL")
    except Exception as exc:
        logger.error(f"Trending snapshot failed: {exc}")


@celery_app.task
def cleanup_expired_platform_cache():
    """Remove expired platform check keys from Redis (Redis handles TTLs, this logs stats)."""
    import redis as sync_redis
    from app.core.config import settings

    r = sync_redis.from_url(settings.REDIS_URL, decode_responses=True)
    keys = r.keys("platform:*")
    logger.info(f"Active platform cache entries: {len(keys)}")
    return {"platform_cache_keys": len(keys)}
