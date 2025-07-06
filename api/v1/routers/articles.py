import hashlib
from typing import Any, Dict, List, Optional

from elasticsearch import Elasticsearch
from fastapi import APIRouter, Depends, HTTPException, Query
from v1.utils import format_elasticsearch_hits, get_elasticsearch_client

router = APIRouter(prefix="/articles", tags=["articles"])


@router.get("/")
async def get_articles(
    limit: int = 10,
    offset: int = 0,
    es: Elasticsearch = Depends(get_elasticsearch_client),
):
    """Get articles from Elasticsearch"""
    try:
        response = es.search(
            index="articles",
            body={"query": {"match_all": {}}, "size": limit, "from": offset},
        )

        articles = format_elasticsearch_hits(response["hits"]["hits"])
        total = response["hits"]["total"]["value"]

        return {"articles": articles, "total": total, "limit": limit, "offset": offset}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch articles: {str(e)}"
        )


@router.get("/search")
async def search_articles(
    q: Optional[str] = Query(
        None, description="Search query for title, content, and topics"
    ),
    author: Optional[str] = Query(None, description="Filter by author"),
    topics: Optional[str] = Query(None, description="Filter by topics"),
    source_section: Optional[str] = Query(None, description="Filter by source section"),
    date_from: Optional[str] = Query(
        None, description="Filter articles published from this date (YYYY-MM-DD)"
    ),
    date_to: Optional[str] = Query(
        None, description="Filter articles published until this date (YYYY-MM-DD)"
    ),
    limit: int = Query(10, ge=1, le=100, description="Number of articles to return"),
    offset: int = Query(0, ge=0, description="Number of articles to skip"),
    es: Elasticsearch = Depends(get_elasticsearch_client),
):
    """Search articles with various filters"""
    try:
        query = {"bool": {"must": []}}

        if q:
            query["bool"]["must"].append(
                {
                    "multi_match": {
                        "query": q,
                        "fields": ["article_title", "article", "topics"],
                        "type": "best_fields",
                        "fuzziness": "AUTO",
                    }
                }
            )

        if author:
            query["bool"]["must"].append({"term": {"author.keyword": author}})

        if topics:
            query["bool"]["must"].append({"match": {"topics": topics}})

        if source_section:
            query["bool"]["must"].append({"match": {"source_section": source_section}})

        if date_from or date_to:
            date_range = {}
            if date_from:
                date_range["gte"] = date_from
            if date_to:
                date_range["lte"] = date_to
            query["bool"]["must"].append({"range": {"published": date_range}})

        # Default to match_all if no filters
        if not query["bool"]["must"]:
            query = {"match_all": {}}

        response = es.search(
            index="articles",
            body={
                "query": query,
                "sort": [{"published": {"order": "desc"}}],
                "size": limit,
                "from": offset,
            },
        )

        articles = format_elasticsearch_hits(response["hits"]["hits"])
        total = response["hits"]["total"]["value"]

        return {
            "articles": articles,
            "total": total,
            "limit": limit,
            "offset": offset,
            "query": query,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@router.get("/timeline")
async def get_publication_timeline(
    interval: str = Query(
        "1d", description="Time interval for aggregation (1d, 1w, 1M, etc.)"
    ),
    source_section: Optional[str] = Query(None, description="Filter by source section"),
    es: Elasticsearch = Depends(get_elasticsearch_client),
):
    """Get article publication timeline"""
    try:
        query = (
            {"match_all": {}}
            if not source_section
            else {"match": {"source_section": source_section}}
        )

        response = es.search(
            index="articles",
            body={
                "size": 0,
                "query": query,
                "aggs": {
                    "publications_over_time": {
                        "date_histogram": {
                            "field": "published",
                            "calendar_interval": interval,
                            "format": "yyyy-MM-dd",
                        }
                    }
                },
            },
        )

        return {
            "timeline": [
                {"date": bucket["key_as_string"], "count": bucket["doc_count"]}
                for bucket in response["aggregations"]["publications_over_time"][
                    "buckets"
                ]
            ],
            "interval": interval,
            "source_section": source_section,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get timeline: {str(e)}")


@router.get("/{article_id}")
async def get_article(
    article_id: str, es: Elasticsearch = Depends(get_elasticsearch_client)
):
    """Get a specific article by ID"""
    try:
        response = es.get(index="articles", id=article_id)
        return {"id": article_id, **response["_source"]}
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Article not found: {str(e)}")


@router.get("/{article_id}/related")
async def get_related_articles(
    article_id: str,
    limit: int = Query(
        5, ge=1, le=20, description="Number of related articles to return"
    ),
    es: Elasticsearch = Depends(get_elasticsearch_client),
):
    """Find articles similar to the given article"""
    try:
        # First check if the article exists
        es.get(index="articles", id=article_id)

        # Find similar articles based on topics and content
        response = es.search(
            index="articles",
            body={
                "query": {
                    "bool": {
                        "must": [
                            {
                                "more_like_this": {
                                    "fields": ["article_title", "article", "topics"],
                                    "like": [{"_index": "articles", "_id": article_id}],
                                    "min_term_freq": 1,
                                    "max_query_terms": 12,
                                    "min_doc_freq": 1,
                                }
                            }
                        ],
                        "must_not": [{"term": {"_id": article_id}}],
                    }
                },
                "size": limit,
            },
        )

        return {
            "article_id": article_id,
            "related_articles": format_elasticsearch_hits(response["hits"]["hits"]),
            "total_found": response["hits"]["total"]["value"],
        }
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Article not found: {str(e)}")


@router.delete("/{article_id}")
async def delete_article(
    article_id: str, es: Elasticsearch = Depends(get_elasticsearch_client)
):
    """Delete a specific article by ID"""
    try:
        response = es.delete(index="articles", id=article_id, refresh="wait_for")
        return {
            "id": article_id,
            "result": response["result"],
            "message": "Article deleted successfully",
        }
    except Exception as e:
        raise HTTPException(
            status_code=404, detail=f"Article not found or delete failed: {str(e)}"
        )


@router.post("/upsert")
async def upsert_article(
    article: Dict[str, Any], es: Elasticsearch = Depends(get_elasticsearch_client)
):
    """Create or update an article based on its title hash"""
    try:
        # Validate required fields
        if "article_title" not in article:
            raise HTTPException(status_code=400, detail="article_title is required")

        # Generate hash-based ID from article title
        article_id = hashlib.md5(article["article_title"].encode("utf-8")).hexdigest()

        # Check if article exists
        try:
            existing = es.get(index="articles", id=article_id)
            # Article exists, update it
            response = es.update(
                index="articles",
                id=article_id,
                body={"doc": article},
                refresh="wait_for",
            )
            return {
                "id": article_id,
                "result": response["result"],
                "message": "Article updated successfully",
                "action": "updated",
            }
        except:
            # Article doesn't exist, create it
            response = es.index(
                index="articles", id=article_id, body=article, refresh="wait_for"
            )
            return {
                "id": article_id,
                "result": response["result"],
                "message": "Article created successfully",
                "action": "created",
            }
    except HTTPException:
        # Re-raise HTTPExceptions
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Upsert operation failed: {str(e)}"
        )


@router.post("/bulk-upsert")
async def bulk_upsert_articles(
    articles: List[Dict[str, Any]],
    es: Elasticsearch = Depends(get_elasticsearch_client),
):
    """Create or update multiple articles in bulk"""
    try:
        if not articles:
            raise HTTPException(status_code=400, detail="No articles provided")

        bulk_data = []
        for article in articles:
            # Validate required fields
            if "article_title" not in article:
                raise HTTPException(
                    status_code=400, detail="article_title is required for all articles"
                )

            # Generate hash-based ID from article title
            article_id = hashlib.md5(
                article["article_title"].encode("utf-8")
            ).hexdigest()
            bulk_data.extend(
                [{"index": {"_index": "articles", "_id": article_id}}, article]
            )

        response = es.bulk(body=bulk_data, refresh="wait_for")

        # Count results
        created = 0
        updated = 0
        errors = []

        for item in response["items"]:
            if "error" in item["index"]:
                errors.append(item["index"]["error"])
            elif item["index"]["result"] == "created":
                created += 1
            elif item["index"]["result"] == "updated":
                updated += 1

        if errors:
            return {
                "status": "partial_success",
                "created": created,
                "updated": updated,
                "errors": len(errors),
                "error_details": errors[:5],  # Limit error details to first 5
            }

        return {
            "status": "success",
            "created": created,
            "updated": updated,
            "message": f"Successfully processed {len(articles)} articles ({created} created, {updated} updated)",
        }
    except HTTPException:
        # Re-raise HTTPExceptions (like the 400 for empty list)
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Bulk upsert operation failed: {str(e)}"
        )
