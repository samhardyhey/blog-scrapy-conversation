import os

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from loguru import logger
from v1.api import api_router

app = FastAPI(title="Blog Scraper API", version="1.0.0")


@app.get("/")
async def root():
    return RedirectResponse(url="/docs")


# Include V1 API
app.include_router(api_router)


if __name__ == "__main__":
    import uvicorn

    # Enable hot reload in development mode
    reload = os.getenv("ENV") == "development"
    port = int(os.getenv("API_PORT", "8001"))

    logger.info(
        f"Starting server in {'development' if reload else 'production'} mode on port {port}"
    )

    if reload:
        # For development with reload, use import string and better file watching
        uvicorn.run(
            "main:app",
            host="0.0.0.0",
            port=port,
            reload=True,
            reload_dirs=["/app"],
            reload_includes=["*.py"],
            log_level="info",
        )
    else:
        # For production, use app object directly
        uvicorn.run(app, host="0.0.0.0", port=port, reload=False)
