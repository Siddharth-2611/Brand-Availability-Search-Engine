from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql+asyncpg://brand:brand123@localhost:5432/branddb"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Elasticsearch
    ELASTICSEARCH_URL: str = "http://localhost:9200"
    ES_INDEX_BRANDS: str = "brands"
    ES_INDEX_USERNAMES: str = "usernames"

    # RabbitMQ / Celery
    CELERY_BROKER_URL: str = "amqp://brand:brand123@localhost:5672/"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"

    # Cache TTLs (seconds)
    CACHE_TTL_USERNAME: int = 3600       # 1 hour
    CACHE_TTL_AUTOCOMPLETE: int = 300    # 5 minutes
    CACHE_TTL_TRENDING: int = 60         # 1 minute

    # Semantic search
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
    FAISS_INDEX_PATH: str = "/tmp/faiss.index"

    # Platform checks
    PLATFORM_CHECK_TIMEOUT: float = 5.0  # seconds per platform
    PLATFORM_CHECK_CONCURRENCY: int = 20  # max simultaneous checks

    class Config:
        env_file = ".env"


settings = Settings()
