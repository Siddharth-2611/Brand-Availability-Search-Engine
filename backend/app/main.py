"""Brand Identity Search Engine — FastAPI entry point."""

import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator

from app.core.config import settings
from app.core.database import init_db
from app.core.redis_client import init_redis
from app.core.elasticsearch_client import init_elasticsearch
from app.api import search, autocomplete, platforms, analytics, health


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    await init_db()
    await init_redis()
    await init_elasticsearch()
    print("✅  All services initialised")
    yield
    print("🛑  Shutting down")


app = FastAPI(
    title="Brand Identity Search Engine",
    description="Google-style brand search with Trie autocomplete, BK-Tree typo correction, BM25 + semantic ranking, and concurrent username availability checks across 50+ platforms.",
    version="1.0.0",
    lifespan=lifespan,
)

# ── CORS ─────────────────────────────────────────────────────────────
# Wide open for local/portfolio use — this is a demo project, not a
# multi-tenant SaaS, and no cookies/credentials are used.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Request timing middleware ─────────────────────────────────────────
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - start) * 1000
    response.headers["X-Process-Time-Ms"] = f"{elapsed_ms:.2f}"
    return response

# ── Prometheus metrics ────────────────────────────────────────────────
Instrumentator().instrument(app).expose(app)

# ── Routers ───────────────────────────────────────────────────────────
app.include_router(health.router,       prefix="/api/v1",           tags=["health"])
app.include_router(search.router,       prefix="/api/v1/search",    tags=["search"])
app.include_router(autocomplete.router, prefix="/api/v1/autocomplete", tags=["autocomplete"])
app.include_router(platforms.router,    prefix="/api/v1/platforms", tags=["platforms"])
app.include_router(analytics.router,    prefix="/api/v1/analytics", tags=["analytics"])


@app.get("/")
async def root():
    return {
        "name": "Brand Identity Search Engine",
        "version": "1.0.0",
        "docs": "/docs",
        "status": "running",
    }
