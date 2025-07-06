from elasticsearch import Elasticsearch
from fastapi import APIRouter, Depends, HTTPException, Query
from v1.utils import format_elasticsearch_hits, get_elasticsearch_client

router = APIRouter(prefix="/topics", tags=["topics"])


@router.get("/{topic}/articles")
async def get_articles_by_topic(
    topic: str,
    limit: int = Query(20, ge=1, le=100, description="Number of articles to return"),
    offset: int = Query(0, ge=0, description="Number of articles to skip"),
    es: Elasticsearch = Depends(get_elasticsearch_client),
):
    """Get all articles for a specific topic"""
    try:
        response = es.search(
            index="articles",
            body={
                "query": {"match": {"topics": topic}},
                "sort": [{"published": {"order": "desc"}}],
                "size": limit,
                "from": offset,
            },
        )

        return {
            "topic": topic,
            "articles": format_elasticsearch_hits(response["hits"]["hits"]),
            "total": response["hits"]["total"]["value"],
            "limit": limit,
            "offset": offset,
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch articles for topic: {str(e)}"
        )


@router.get("/popular")
async def get_popular_topics(
    limit: int = Query(
        10, ge=1, le=50, description="Number of popular topics to return"
    ),
    es: Elasticsearch = Depends(get_elasticsearch_client),
):
    """Get most frequently occurring topics"""
    try:
        response = es.search(
            index="articles",
            body={
                "size": 0,
                "aggs": {
                    "topics": {
                        "terms": {
                            "field": "topics.keyword",
                            "size": limit,
                            "order": {"_count": "desc"},
                        }
                    }
                },
            },
        )

        return {
            "popular_topics": [
                {"topic": bucket["key"], "count": bucket["doc_count"]}
                for bucket in response["aggregations"]["topics"]["buckets"]
            ]
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get popular topics: {str(e)}"
        )
