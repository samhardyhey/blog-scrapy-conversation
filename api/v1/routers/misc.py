from datetime import datetime

from elasticsearch import Elasticsearch
from fastapi import APIRouter, Depends, HTTPException
from v1.utils import get_elasticsearch_client

router = APIRouter(prefix="/misc", tags=["misc"])


@router.get("/health")
async def health_check():
    """Basic API health check - fast response, no external dependencies"""
    return {
        "status": "healthy",
        "service": "blog-scraper-api",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.get("/health/ready")
async def readiness_check(es: Elasticsearch = Depends(get_elasticsearch_client)):
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


@router.get("/health/live")
async def liveness_check():
    """Liveness check - verifies the API process is alive"""
    return {
        "status": "alive",
        "service": "blog-scraper-api",
        "timestamp": datetime.utcnow().isoformat(),
    }
