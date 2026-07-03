# 🔍 Brand Identity Search Engine

A distributed, fully local brand-name search engine that checks name availability
across 27 platforms and 6 domain TLDs **concurrently**, with Google-style
autocomplete, typo correction, and hybrid lexical + semantic ranking — all
backed by hand-implemented data structures, not off-the-shelf libraries.

Built as a systems-design portfolio piece: every core algorithm (Trie, BK-Tree,
BM25 inverted index, trending heap) is written from scratch and unit-tested,
sitting inside a real microservices architecture (FastAPI, Postgres, Redis,
Elasticsearch, RabbitMQ, Celery) that runs entirely with Docker Compose —
no cloud account, no API keys, no paid services required.

---

## ✨ What it does

- Type a brand/username idea → see availability across **GitHub, Instagram,
  Reddit, Twitch, Discord, LinkedIn, and 20+ more platforms simultaneously**
- Domain availability across `.com` `.io` `.dev` `.ai` `.co` `.app`
- Autocomplete suggestions ranked by real search frequency (learns from usage)
- "Did you mean…?" typo correction via edit-distance matching
- Hybrid search combining keyword relevance (BM25) and semantic similarity (embeddings)
- Live trending leaderboard of recently searched names
- Sub-second responses via Redis caching + concurrent async I/O

## 🧱 Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.12 |
| API | FastAPI + uvicorn |
| Frontend | Plain HTML / CSS / JS — zero build step, zero dependencies |
| Database | PostgreSQL 16 |
| Cache | Redis 7 |
| Search | Elasticsearch 8 |
| Semantic Search | sentence-transformers + FAISS |
| Async HTTP | aiohttp (concurrent platform checks) |
| Background Jobs | Celery |
| Message Queue | RabbitMQ |
| Monitoring | Prometheus + Grafana |
| Containers | Docker Compose (9 services, one command to run) |

## 🧠 Data Structures & Algorithms — implemented from scratch

| Structure | File | Purpose | Complexity |
|---|---|---|---|
| **Trie** | `algorithms/trie.py` | Autocomplete, frequency-ranked | O(k) insert/search |
| **BK-Tree** | `algorithms/bk_tree.py` | Typo correction (Levenshtein + triangle-inequality pruning) | O(n^0.3) avg query |
| **Inverted Index + BM25** | `algorithms/inverted_index.py` | Full-text ranking, phrase search | O(\|q\| × \|matches\|) |
| **Max-Heap + HashMap** | `algorithms/trending_heap.py` | Real-time top-K leaderboard | O(1) lookup, O(log K) update |
| **Concurrent checker** | `services/platform_checker.py` | 33 simultaneous availability checks via `asyncio.gather()` | O(1) wall-clock vs O(n) sequential |
| **Semantic search** | `services/semantic_search.py` | FAISS + sentence-transformers, RRF-fused with BM25 | sub-ms ANN lookup |

All four core structures have a full unit test suite (`backend/tests/test_algorithms.py`, 28 tests).

Autocomplete and typo-correction are corpus-based, not dictionaries — they
suggest words the system has actually seen (seeded on first boot, then learned
from every real search), exactly like Google/Amazon-style autocomplete.

## 🚀 Quick Start

```bash
git clone <repo>
cd brand-search
cp .env.example .env
docker compose up --build
```

Wait for `✅ All services initialised` in the `api` logs (Elasticsearch is the slowest to boot — give it 1–2 minutes on first run).

| Service | URL |
|---|---|
| **App** | http://localhost:3000 |
| **API docs (Swagger)** | http://localhost:8000/docs |
| **RabbitMQ dashboard** | http://localhost:15672 (`brand` / `brand123`) |
| **Grafana** | http://localhost:3001 (`admin` / `admin123`) |
| **Prometheus** | http://localhost:9090 |

The frontend is a single `frontend/index.html` file, served by a plain nginx
container — no npm install, no build step, no framework.

## 📡 API Endpoints

```
GET /api/v1/search?q=bytebot          Full search (BM25 + semantic + trending)
GET /api/v1/autocomplete?q=byte       Trie autocomplete
GET /api/v1/search/platforms/bytebot  Concurrent platform + domain availability check
GET /api/v1/platforms                 List all supported platforms/domains
GET /api/v1/analytics/trending        Top-K trending heap
GET /api/v1/analytics/trie/stats      Trie statistics
GET /api/v1/analytics/index/stats     Inverted index statistics
GET /api/v1/health                    Service health check
GET /metrics                          Prometheus metrics
```

## 🧪 Running Tests

```bash
cd backend
pip install -r requirements.txt
pytest tests/ -v
```

28 tests covering Trie, BK-Tree, trending heap, and BM25 inverted index — insert/search/delete correctness, ranking order, edge cases.

## 🏗️ Architecture

```
Browser
  │
  ▼
Static frontend (nginx, port 3000) — plain HTML/CSS/JS
  │
  ▼
FastAPI (port 8000)
  │
  ├── Redis (cache: autocomplete, platform checks, search results)
  ├── PostgreSQL (persistence: searches, analytics, trending snapshots)
  ├── Elasticsearch (BM25 full-text ranking)
  └── RabbitMQ → Celery Workers
                    ├── Platform + domain checker (asyncio, 33 concurrent)
                    ├── Elasticsearch indexer
                    └── Trending snapshot to PostgreSQL
```

## 📁 Project Structure

```
brand-search/
├── docker-compose.yml
├── backend/
│   ├── app/
│   │   ├── algorithms/     # Trie, BK-Tree, inverted index, trending heap
│   │   ├── services/       # platform checker, semantic search, search orchestration
│   │   ├── api/            # FastAPI routers
│   │   ├── core/           # config, DB/Redis/ES clients
│   │   └── workers/        # Celery background jobs
│   └── tests/
├── frontend/
│   └── index.html          # entire frontend, zero dependencies
├── postgres/
│   └── init.sql            # schema
└── analytics/               # Prometheus + Grafana config
```

## 🎯 What This Project Demonstrates

| Topic | Where |
|---|---|
| Autocomplete design | `algorithms/trie.py` |
| Fuzzy / typo-tolerant search | `algorithms/bk_tree.py` |
| BM25 ranking, from first principles | `algorithms/inverted_index.py` |
| Real-time leaderboards | `algorithms/trending_heap.py` |
| High-concurrency I/O with asyncio | `services/platform_checker.py` |
| Vector / semantic search | `services/semantic_search.py` |
| Caching strategy | Redis TTLs throughout |
| Microservices + message queues | `workers/` + RabbitMQ |
| Schema design | `postgres/init.sql` |
| Observability | Prometheus + Grafana |

## 🛠️ Troubleshooting

**Same platforms every time / autocomplete does nothing**
The API is unreachable — a red banner appears in the UI when this happens
instead of silently faking results. Check the browser console, confirm
`http://localhost:8000/docs` loads directly, and check `docker compose logs api`.

**API container crashes on startup / connection errors to redis or elasticsearch**
Usually a Docker networking or startup-ordering issue. Try:
```bash
docker compose down -v --remove-orphans
docker compose up --build -d
```

**Port already allocated**
Something else on your machine is already using that port. Check
`docker ps -a` for orphaned containers, or remap the port in `docker-compose.yml`.

## 📄 License

MIT — free to use for learning, portfolio, or interview prep.
