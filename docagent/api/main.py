"""Main FastAPI application entry point for DocAgent."""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from docagent.api.routes.jobs import router as jobs_router
from docagent.api.routes.webhooks import router as webhooks_router
from docagent.core.config import settings
from docagent.core.logging import logger
from docagent.database.connection import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle event handler for database initialization and cleanup."""
    logger.info("Initializing DocAgent application and database schema...")
    try:
        init_db()
    except Exception as e:
        logger.warning(f"Could not initialize database on startup (offline/memory mode): {e}")
    yield
    logger.info("DocAgent application shutdown complete.")


def create_app() -> FastAPI:
    """Factory creating configured FastAPI instance."""
    app = FastAPI(
        title=settings.APP_NAME,
        version="0.1.0",
        description="Production Intelligent Documentation Agent API.",
        lifespan=lifespan,
    )

    # CORS configuration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Attach API v1 routers
    app.include_router(webhooks_router, prefix="/api/v1")
    app.include_router(jobs_router, prefix="/api/v1")

    @app.get("/healthz", tags=["Health"])
    async def health_check():
        """Health check endpoint for container orchestrators and monitoring."""
        return {
            "status": "healthy",
            "environment": settings.ENVIRONMENT,
            "version": "0.1.0",
        }

    return app


app = create_app()
