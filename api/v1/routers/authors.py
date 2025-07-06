from elasticsearch import Elasticsearch
from fastapi import APIRouter, Depends, HTTPException, Query
from v1.utils import format_elasticsearch_hits, get_elasticsearch_client

router = APIRouter(prefix="/authors", tags=["authors"])


@router.get("/{author}/articles")
async def get_articles_by_author(
    author: str,
    limit: int = Query(20, ge=1, le=100, description="Number of articles to return"),
    offset: int = Query(0, ge=0, description="Number of articles to skip"),
    es: Elasticsearch = Depends(get_elasticsearch_client),
):
    """Get all articles by a specific author"""
    try:
        response = es.search(
            index="articles",
            body={
                "query": {"match": {"author": author}},
                "sort": [{"published": {"order": "desc"}}],
                "size": limit,
                "from": offset,
            },
        )

        return {
            "author": author,
            "articles": format_elasticsearch_hits(response["hits"]["hits"]),
            "total": response["hits"]["total"]["value"],
            "limit": limit,
            "offset": offset,
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch articles by author: {str(e)}"
        )
