from fastapi import APIRouter
from v1.routers import articles, authors, misc, stats, topics

# Create V1 API router
api_router = APIRouter(prefix="/v1")

# Include all routers
api_router.include_router(articles.router)
api_router.include_router(authors.router)
api_router.include_router(topics.router)
api_router.include_router(stats.router)
api_router.include_router(misc.router)
