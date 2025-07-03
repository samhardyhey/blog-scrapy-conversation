from fastapi import FastAPI, HTTPException
from elasticsearch import Elasticsearch
import os
import json
from typing import List, Dict, Any

app = FastAPI(title="Blog Scraper API", version="1.0.0")

# Elasticsearch connection
es_host = os.getenv("ELASTICSEARCH_HOST", "elasticsearch")
es_port = os.getenv("ELASTICSEARCH_PORT", "9200")

es = Elasticsearch([f"http://{es_host}:{es_port}"])

@app.get("/")
async def root():
    return {"message": "Blog Scraper API is running"}

@app.get("/health")
async def health_check():
    try:
        # Check Elasticsearch connection
        es_info = es.info()
        return {
            "status": "healthy",
            "elasticsearch": "connected",
            "es_version": es_info.get("version", {}).get("number", "unknown")
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Elasticsearch connection failed: {str(e)}")

@app.get("/articles")
async def get_articles(limit: int = 10, offset: int = 0):
    """Get articles from Elasticsearch"""
    try:
        # Search for articles in Elasticsearch
        response = es.search(
            index="articles",
            body={
                "query": {"match_all": {}},
                "size": limit,
                "from": offset
            }
        )

        articles = [hit["_source"] for hit in response["hits"]["hits"]]
        total = response["hits"]["total"]["value"]

        return {
            "articles": articles,
            "total": total,
            "limit": limit,
            "offset": offset
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch articles: {str(e)}")

@app.get("/articles/{article_id}")
async def get_article(article_id: str):
    """Get a specific article by ID"""
    try:
        response = es.get(index="articles", id=article_id)
        return response["_source"]
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Article not found: {str(e)}")

@app.post("/articles")
async def create_article(article: Dict[str, Any]):
    """Create a new article in Elasticsearch"""
    try:
        response = es.index(index="articles", body=article)
        return {
            "id": response["_id"],
            "result": response["result"],
            "message": "Article created successfully"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create article: {str(e)}")

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
                "aggs": {
                    "avg_length": {
                        "avg": {
                            "field": "content_length"
                        }
                    }
                }
            }
        )

        return {
            "total_articles": total_articles,
            "average_content_length": stats_response["aggregations"]["avg_length"]["value"]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)