from elasticsearch import AsyncElasticsearch
from app.core.config import settings

_es: AsyncElasticsearch | None = None

BRANDS_MAPPING = {
    "mappings": {
        "properties": {
            "name":        {"type": "text",    "analyzer": "standard"},
            "description": {"type": "text",    "analyzer": "english"},
            "category":    {"type": "keyword"},
            "tags":        {"type": "keyword"},
            "embedding":   {"type": "dense_vector", "dims": 384, "index": True, "similarity": "cosine"},
            "created_at":  {"type": "date"},
        }
    },
    "settings": {
        "number_of_shards": 1,
        "number_of_replicas": 0,
        "analysis": {
            "analyzer": {
                "autocomplete_analyzer": {
                    "type": "custom",
                    "tokenizer": "edge_ngram_tokenizer",
                    "filter": ["lowercase"],
                },
            },
            "tokenizer": {
                "edge_ngram_tokenizer": {
                    "type": "edge_ngram",
                    "min_gram": 1,
                    "max_gram": 20,
                    "token_chars": ["letter", "digit"],
                }
            },
        },
    },
}


async def init_elasticsearch():
    global _es
    _es = AsyncElasticsearch([settings.ELASTICSEARCH_URL])
    info = await _es.info()
    print(f"✅  Elasticsearch connected — version {info['version']['number']}")

    # Create index if missing
    if not await _es.indices.exists(index=settings.ES_INDEX_BRANDS):
        await _es.indices.create(index=settings.ES_INDEX_BRANDS, body=BRANDS_MAPPING)
        print(f"   Created index: {settings.ES_INDEX_BRANDS}")


def get_es() -> AsyncElasticsearch:
    if _es is None:
        raise RuntimeError("Elasticsearch not initialised")
    return _es
