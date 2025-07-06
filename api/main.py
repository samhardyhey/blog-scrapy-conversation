import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from elasticsearch import Elasticsearch
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import RedirectResponse
from loguru import logger

app = FastAPI(title="Blog Scraper API", version="1.0.0")

# Elasticsearch connection
es_host = os.getenv("ELASTICSEARCH_HOST", "elasticsearch")
es_port = os.getenv("ELASTICSEARCH_PORT", "9200")

es = Elasticsearch([f"http://{es_host}:{es_port}"])


def format_elasticsearch_hits(hits):
    """Format Elasticsearch hits to include both ID and source content"""
    return [{"id": hit["_id"], **hit["_source"]} for hit in hits]


@app.get("/")
async def root():
    return RedirectResponse(url="/docs")


@app.get("/health")
async def health_check():
    """Basic API health check - fast response, no external dependencies"""
    return {
        "status": "healthy",
        "service": "blog-scraper-api",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.get("/health/ready")
async def readiness_check():
    """Readiness check - verifies the API can serve requests (includes Elasticsearch)"""
    try:
        # Check Elasticsearch connection
        es_info = es.info()
        return {
            "status": "ready",
            "service": "blog-scraper-api",
            "version": "1.0.0",
            "timestamp": datetime.utcnow().isoformat(),
            "dependencies": {
                "elasticsearch": {
                    "status": "connected",
                    "version": es_info.get("version", {}).get("number", "unknown"),
                    "cluster_name": es_info.get("cluster_name", "unknown"),
                }
            },
        }
    except Exception as e:
        raise HTTPException(
            status_code=503,  # Service Unavailable
            detail=f"Service not ready: Elasticsearch connection failed - {str(e)}",
        )


@app.get("/health/live")
async def liveness_check():
    """Liveness check - verifies the API process is alive"""
    return {
        "status": "alive",
        "service": "blog-scraper-api",
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.get("/articles")
async def get_articles(limit: int = 10, offset: int = 0):
    """Get articles from Elasticsearch"""
    try:
        # Search for articles in Elasticsearch
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


@app.get("/articles/search")
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
            query["bool"]["must"].append({"match": {"author": author}})

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


@app.get("/articles/{article_id}")
async def get_article(article_id: str):
    """Get a specific article by ID"""
    try:
        response = es.get(index="articles", id=article_id)
        return {"id": article_id, **response["_source"]}
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Article not found: {str(e)}")


@app.get("/articles/{article_id}/related")
async def get_related_articles(
    article_id: str,
    limit: int = Query(
        5, ge=1, le=20, description="Number of related articles to return"
    ),
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


@app.post("/articles")
async def create_article(article: Dict[str, Any]):
    """Create a new article in Elasticsearch"""
    try:
        # Generate hash-based ID from article title
        import hashlib

        article_id = hashlib.md5(article["article_title"].encode("utf-8")).hexdigest()
        response = es.index(index="articles", id=article_id, body=article)
        return {
            "id": response["_id"],
            "result": response["result"],
            "message": "Article created successfully",
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to create article: {str(e)}"
        )


@app.get("/topics/{topic}/articles")
async def get_articles_by_topic(
    topic: str,
    limit: int = Query(20, ge=1, le=100, description="Number of articles to return"),
    offset: int = Query(0, ge=0, description="Number of articles to skip"),
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


@app.get("/topics/popular")
async def get_popular_topics(
    limit: int = Query(
        10, ge=1, le=50, description="Number of popular topics to return"
    )
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


@app.get("/authors/{author}/articles")
async def get_articles_by_author(
    author: str,
    limit: int = Query(20, ge=1, le=100, description="Number of articles to return"),
    offset: int = Query(0, ge=0, description="Number of articles to skip"),
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


@app.get("/stats")
async def get_stats():
    """Get statistics about the articles"""
    try:
        # Get document count
        count_response = es.count(index="articles")
        total_articles = count_response["count"]

        # Get some basic stats
        stats_response = es.search(
            index="articles",
            body={
                "size": 0,
                "aggs": {"avg_length": {"avg": {"field": "content_length"}}},
            },
        )

        return {
            "total_articles": total_articles,
            "average_content_length": stats_response["aggregations"]["avg_length"][
                "value"
            ],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")


@app.get("/articles/timeline")
async def get_publication_timeline(
    interval: str = Query(
        "1d", description="Time interval for aggregation (1d, 1w, 1M, etc.)"
    ),
    source_section: Optional[str] = Query(None, description="Filter by source section"),
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


@app.post("/articles/bulk")
async def bulk_create_articles(articles: List[Dict[str, Any]]):
    """Create multiple articles in bulk"""
    try:
        if not articles:
            raise HTTPException(status_code=400, detail="No articles provided")

        bulk_data = []
        for article in articles:
            # Generate hash-based ID from article title
            import hashlib

            article_id = hashlib.md5(
                article["article_title"].encode("utf-8")
            ).hexdigest()
            bulk_data.extend(
                [{"index": {"_index": "articles", "_id": article_id}}, article]
            )

        response = es.bulk(body=bulk_data)

        # Check for errors
        errors = [item for item in response["items"] if "error" in item["index"]]
        if errors:
            return {
                "status": "partial_success",
                "created": len(articles) - len(errors),
                "errors": len(errors),
                "error_details": errors[:5],  # Limit error details to first 5
            }

        return {
            "status": "success",
            "created": len(articles),
            "message": f"Successfully created {len(articles)} articles",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Bulk operation failed: {str(e)}")


@app.put("/articles/{article_id}")
async def update_article(article_id: str, article_update: Dict[str, Any]):
    """Update an existing article"""
    try:
        response = es.update(
            index="articles", id=article_id, body={"doc": article_update}
        )
        return {
            "id": article_id,
            "result": response["result"],
            "message": "Article updated successfully",
        }
    except Exception as e:
        raise HTTPException(
            status_code=404, detail=f"Article not found or update failed: {str(e)}"
        )


@app.delete("/articles/{article_id}")
async def delete_article(article_id: str):
    """Delete a specific article by ID"""
    try:
        response = es.delete(index="articles", id=article_id)
        return {
            "id": article_id,
            "result": response["result"],
            "message": "Article deleted successfully",
        }
    except Exception as e:
        raise HTTPException(
            status_code=404, detail=f"Article not found or delete failed: {str(e)}"
        )


@app.post("/articles/upsert")
async def upsert_article(article: Dict[str, Any]):
    """Create or update an article based on its title hash"""
    try:
        # Generate hash-based ID from article title
        import hashlib

        article_id = hashlib.md5(article["article_title"].encode("utf-8")).hexdigest()

        # Check if article exists
        try:
            existing = es.get(index="articles", id=article_id)
            # Article exists, update it
            response = es.update(index="articles", id=article_id, body={"doc": article})
            return {
                "id": article_id,
                "result": response["result"],
                "message": "Article updated successfully",
                "action": "updated",
            }
        except:
            # Article doesn't exist, create it
            response = es.index(index="articles", id=article_id, body=article)
            return {
                "id": article_id,
                "result": response["result"],
                "message": "Article created successfully",
                "action": "created",
            }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Upsert operation failed: {str(e)}"
        )


@app.post("/articles/bulk-upsert")
async def bulk_upsert_articles(articles: List[Dict[str, Any]]):
    """Create or update multiple articles in bulk"""
    try:
        if not articles:
            raise HTTPException(status_code=400, detail="No articles provided")

        bulk_data = []
        for article in articles:
            # Generate hash-based ID from article title
            import hashlib

            article_id = hashlib.md5(
                article["article_title"].encode("utf-8")
            ).hexdigest()
            bulk_data.extend(
                [{"index": {"_index": "articles", "_id": article_id}}, article]
            )

        response = es.bulk(body=bulk_data)

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
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Bulk upsert operation failed: {str(e)}"
        )


if __name__ == "__main__":
    import uvicorn

    # Enable hot reload in development mode
    reload = os.getenv("ENV") == "development"
    logger.info(f"Starting server in {'development' if reload else 'production'} mode")

    if reload:
        # For development with reload, use import string
        uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("API_PORT")), reload=True)
    else:
        # For production, use app object directly
        uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("API_PORT")), reload=False)
