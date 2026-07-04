from fastapi import APIRouter
from app.core.redis_client import get_redis
from app.core.elasticsearch_client import get_es

router = APIRouter()


@router.get("/health")
async def health():
    checks = {}

    # Redis
    try:
        await get_redis().ping()
        checks["redis"] = "ok"
    except Exception as e:
        checks["redis"] = f"error: {e}"

    # Elasticsearch
    try:
        info = await get_es().info()
        checks["elasticsearch"] = f"ok ({info['version']['number']})"
    except Exception as e:
        checks["elasticsearch"] = f"error: {e}"

    overall = "healthy" if all("error" not in v for v in checks.values()) else "degraded"
    return {"status": overall, "checks": checks}
