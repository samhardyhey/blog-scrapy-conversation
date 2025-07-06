import os
from functools import lru_cache

from elasticsearch import Elasticsearch


def format_elasticsearch_hits(hits):
    """Format Elasticsearch hits to include both ID and source content"""
    return [{"id": hit["_id"], **hit["_source"]} for hit in hits]


@lru_cache()
def get_elasticsearch_client() -> Elasticsearch:
    """Get Elasticsearch client instance"""
    es_host = os.getenv("ELASTICSEARCH_HOST", "elasticsearch")
    es_port = os.getenv("ELASTICSEARCH_PORT", "9200")
    return Elasticsearch([f"http://{es_host}:{es_port}"])
