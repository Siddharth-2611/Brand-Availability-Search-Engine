"""
Celery Background Worker
========================
Handles long-running tasks that shouldn't block the FastAPI request cycle:
  - Bulk platform checks
  - Elasticsearch document indexing
  - Trending leaderboard snapshot to PostgreSQL
  - FAISS index rebuild
"""

from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "brand_search",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    worker_prefetch_multiplier=1,   # fair task distribution
    task_acks_late=True,            # only ack after successful completion
    # Beat schedule for periodic tasks
    beat_schedule={
        "snapshot-trending-every-minute": {
            "task": "app.workers.tasks.snapshot_trending",
            "schedule": 60.0,
        },
        "cleanup-expired-cache-every-hour": {
            "task": "app.workers.tasks.cleanup_expired_platform_cache",
            "schedule": 3600.0,
        },
    },
)
