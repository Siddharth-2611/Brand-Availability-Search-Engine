import redis.asyncio as aioredis
from app.core.config import settings

_redis: aioredis.Redis | None = None


async def init_redis():
    global _redis
    _redis = aioredis.from_url(
        settings.REDIS_URL,
        encoding="utf-8",
        decode_responses=True,
        max_connections=20,
    )
    await _redis.ping()
    print("✅  Redis connected")


def get_redis() -> aioredis.Redis:
    if _redis is None:
        raise RuntimeError("Redis not initialised")
    return _redis
