from elasticsearch import Elasticsearch
from fastapi import APIRouter, Depends, HTTPException
from v1.utils import get_elasticsearch_client

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("/")
async def get_stats(es: Elasticsearch = Depends(get_elasticsearch_client)):
    """Get comprehensive statistics about the articles"""
    try:
        # Get document count
        count_response = es.count(index="articles")
        total_articles = count_response["count"]

        # Get comprehensive stats with multiple aggregations
        stats_response = es.search(
            index="articles",
            body={
                "size": 0,
                "aggs": {
                    "avg_length": {"avg": {"field": "content_length"}},
                    "authors": {
                        "terms": {
                            "field": "author.keyword",
                            "size": 20,
                            "order": {"_count": "desc"},
                        }
                    },
                    "source_sections": {
                        "terms": {
                            "field": "source_section.keyword",
                            "size": 20,
                            "order": {"_count": "desc"},
                        }
                    },
                    "publication_timeline": {
                        "date_histogram": {
                            "field": "published",
                            "calendar_interval": "1M",
                            "format": "yyyy-MM",
                        }
                    },
                    "ingestion_timeline": {
                        "date_histogram": {
                            "field": "_timestamp",
                            "calendar_interval": "1M",
                            "format": "yyyy-MM",
                        }
                    },
                    "topics": {
                        "terms": {
                            "field": "topics.keyword",
                            "size": 20,
                            "order": {"_count": "desc"},
                        }
                    },
                },
            },
        )

        aggs = stats_response["aggregations"]

        return {
            "total_articles": total_articles,
            "average_content_length": aggs["avg_length"]["value"],
            "author_stats": {
                "total_authors": len(aggs["authors"]["buckets"]),
                "top_authors": [
                    {"author": bucket["key"], "article_count": bucket["doc_count"]}
                    for bucket in aggs["authors"]["buckets"][:10]
                ],
            },
            "department_stats": {
                "total_departments": len(aggs["source_sections"]["buckets"]),
                "top_departments": [
                    {"department": bucket["key"], "article_count": bucket["doc_count"]}
                    for bucket in aggs["source_sections"]["buckets"]
                ],
            },
            "publication_stats": {
                "timeline": [
                    {"month": bucket["key_as_string"], "count": bucket["doc_count"]}
                    for bucket in aggs["publication_timeline"]["buckets"]
                ]
            },
            "ingestion_stats": {
                "timeline": [
                    {"month": bucket["key_as_string"], "count": bucket["doc_count"]}
                    for bucket in aggs["ingestion_timeline"]["buckets"]
                ]
            },
            "topic_stats": {
                "total_topics": len(aggs["topics"]["buckets"]),
                "top_topics": [
                    {"topic": bucket["key"], "article_count": bucket["doc_count"]}
                    for bucket in aggs["topics"]["buckets"][:10]
                ],
            },
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")
