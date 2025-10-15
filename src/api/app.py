"""FastAPI application for Scholar Slack Bot REST API.

This module provides the main FastAPI application with all routes,
middleware, exception handlers, and OpenAPI documentation.
"""

import os
import sys
import time
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.api.models import HealthResponse, VersionResponse, ErrorResponse, StatisticsResponse
from src.api.routes import authors_router, publications_router, plugins_router
from src.api.deps import get_authors_db, get_publications_db, get_plugin_registry

logger = logging.getLogger(__name__)

# Application metadata
API_VERSION = "1.0.0"
APP_VERSION = "1.0.0"
START_TIME = time.time()


# ============================================================================
# Lifespan Management
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager.

    Handles startup and shutdown events.
    """
    # Startup
    logger.info(f"Starting Scholar Slack Bot API v{API_VERSION}")

    # Initialize plugin registry and register plugins
    try:
        # Use the canonical Slack plugin (man-in-the-middle over old slack_bot)
        from plugins.slack import SlackPlugin
        registry = get_plugin_registry()
        registry.register(SlackPlugin)
        logger.info("Registered Slack plugin")
    except Exception as e:
        logger.warning(f"Failed to register Slack plugin: {e}")

    yield

    # Shutdown
    logger.info("Shutting down Scholar Slack Bot API")


# ============================================================================
# FastAPI Application
# ============================================================================

app = FastAPI(
    title="Scholar Slack Bot API",
    description="""
    REST API for the Scholar Publication Monitoring Bot.

    This API provides endpoints for:
    - **Authors**: Manage monitored authors
    - **Publications**: Query and filter publications
    - **Plugins**: Configure messaging platform plugins
    - **System**: Health checks and statistics

    ## Authentication

    The API supports optional authentication via API key:
    - Set the `API_KEY` environment variable to enable authentication
    - Provide the key via `X-API-Key` header or `Bearer` token
    - If no `API_KEY` is set, all requests are allowed (development mode)

    ## Rate Limiting

    Rate limiting will be implemented in a future version.

    ## Examples

    ### List all authors
    ```bash
    curl http://localhost:8000/api/v1/authors
    ```

    ### Add a new author
    ```bash
    curl -X POST http://localhost:8000/api/v1/authors \\
         -H "Content-Type: application/json" \\
         -d '{"scholar_id": "abc123xyz"}'
    ```

    ### Query publications
    ```bash
    curl "http://localhost:8000/api/v1/publications?min_year=2023&min_citations=10"
    ```

    ### Configure a plugin
    ```bash
    curl -X PUT http://localhost:8000/api/v1/plugins/slack/config \\
         -H "Content-Type: application/json" \\
         -d '{"config": {"api_token": "xoxb-...", "channel": "#general"}}'
    ```
    """,
    version=API_VERSION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    contact={
        "name": "Scholar Slack Bot",
        "url": "https://github.com/yourusername/scholar-slack-bot",
    },
    license_info={
        "name": "MIT License",
        "url": "https://opensource.org/licenses/MIT",
    },
)


# ============================================================================
# Middleware
# ============================================================================

# CORS - Allow all origins for now (restrict in production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure based on deployment
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all incoming requests."""
    start_time = time.time()

    # Process request
    response = await call_next(request)

    # Log request details
    process_time = time.time() - start_time
    logger.info(
        f"{request.method} {request.url.path} "
        f"status={response.status_code} "
        f"duration={process_time:.3f}s"
    )

    # Add custom header
    response.headers["X-Process-Time"] = str(process_time)

    return response


# ============================================================================
# Exception Handlers
# ============================================================================

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation errors."""
    logger.warning(f"Validation error: {exc}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "ValidationError",
            "message": "Request validation failed",
            "detail": exc.errors()
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle uncaught exceptions."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "InternalServerError",
            "message": "An unexpected error occurred",
            "detail": str(exc) if os.getenv("DEBUG") else None
        }
    )


# ============================================================================
# Root Routes
# ============================================================================

@app.get("/api")
async def api_root():
    """API root endpoint."""
    return {
        "name": "Scholar Slack Bot API",
        "version": API_VERSION,
        "status": "operational",
        "documentation": "/docs",
        "endpoints": {
            "health": "/api/v1/health",
            "version": "/api/v1/version",
            "authors": "/api/v1/authors",
            "publications": "/api/v1/publications",
            "plugins": "/api/v1/plugins",
            "stats": "/api/v1/stats",
        }
    }


# ============================================================================
# System Routes
# ============================================================================

@app.get(
    "/api/v1/health",
    response_model=HealthResponse,
    summary="Health check",
    description="Check the health status of the API and its dependencies.",
    tags=["system"]
)
async def health_check():
    """Health check endpoint.

    Returns:
        HealthResponse: Service health status

    Example:
        ```bash
        curl http://localhost:8000/api/v1/health
        ```
    """
    # Check database connections
    database_ok = True
    try:
        # Test authors DB
        db_gen = get_authors_db()
        authors_db = next(db_gen)
        authors_db.execute("SELECT 1").fetchone()

        # Test publications DB
        pub_db_gen = get_publications_db()
        pub_db = next(pub_db_gen)
        pub_db.execute("SELECT 1").fetchone()

    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        database_ok = False

    # Determine overall status
    if database_ok:
        service_status = "healthy"
    else:
        service_status = "unhealthy"

    uptime = time.time() - START_TIME

    return HealthResponse(
        status=service_status,
        version=API_VERSION,
        uptime_seconds=uptime,
        database_ok=database_ok
    )


@app.get(
    "/api/v1/version",
    response_model=VersionResponse,
    summary="Version information",
    description="Get version information for the API and application.",
    tags=["system"]
)
async def version_info():
    """Get version information.

    Returns:
        VersionResponse: Version details

    Example:
        ```bash
        curl http://localhost:8000/api/v1/version
        ```
    """
    return VersionResponse(
        api_version=API_VERSION,
        app_version=APP_VERSION,
        python_version=f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    )


@app.get(
    "/api/v1/stats",
    response_model=StatisticsResponse,
    summary="Overall statistics",
    description="Get aggregate statistics about the system.",
    tags=["system"]
)
async def get_statistics():
    """Get overall system statistics.

    Returns:
        StatisticsResponse: System statistics

    Example:
        ```bash
        curl http://localhost:8000/api/v1/stats
        ```
    """
    try:
        # Get authors count
        authors_db_gen = get_authors_db()
        authors_db = next(authors_db_gen)
        cursor = authors_db.execute("SELECT COUNT(*) as count FROM authors")
        total_authors = cursor.fetchone()["count"]

        # Get publications count and citations
        pub_db_gen = get_publications_db()
        pub_db = next(pub_db_gen)

        cursor = pub_db.execute("SELECT COUNT(*) as count FROM publications")
        total_publications = cursor.fetchone()["count"]

        cursor = pub_db.execute("SELECT SUM(citations) as total FROM publications")
        total_citations = cursor.fetchone()["total"] or 0

        # Get plugin stats
        registry = get_plugin_registry()
        configured_plugins = len([p for p in registry.list_plugins()
                                  if registry.get_instance(p) is not None])

        return StatisticsResponse(
            total_authors=total_authors,
            total_publications=total_publications,
            total_citations=int(total_citations),
            active_jobs=0,  # TODO: Implement jobs
            configured_plugins=configured_plugins
        )

    except Exception as e:
        logger.error(f"Error retrieving statistics: {e}")
        return StatisticsResponse(
            total_authors=0,
            total_publications=0,
            total_citations=0,
            active_jobs=0,
            configured_plugins=0
        )


# ============================================================================
# API Routes
# ============================================================================

# Mount API routers with v1 prefix
app.include_router(authors_router, prefix="/api/v1")
app.include_router(publications_router, prefix="/api/v1")
app.include_router(plugins_router, prefix="/api/v1")

# Mount web UI routes
try:
    from src.web.routes import router as web_router
    app.include_router(web_router)
    logger.info("Web UI routes mounted")

    # Mount static files
    static_path = os.path.join(os.path.dirname(__file__), "../web/static")
    if os.path.exists(static_path):
        app.mount("/static", StaticFiles(directory=static_path), name="static")
        logger.info("Static files mounted")
except Exception as e:
    logger.warning(f"Failed to mount web UI: {e}")


# ============================================================================
# Main Entry Point
# ============================================================================

if __name__ == "__main__":
    import uvicorn

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Run server
    uvicorn.run(
        "app:app",
        host=os.getenv("API_HOST", "0.0.0.0"),
        port=int(os.getenv("API_PORT", 8000)),
        reload=os.getenv("DEBUG", "false").lower() == "true",
        log_level="info"
    )
