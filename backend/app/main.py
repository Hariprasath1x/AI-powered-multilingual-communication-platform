import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from app.core.config import settings
from app.core.logging_config import setup_pii_redacting_logger
from app.routers import (
    health,
    auth,
    admin_users,
    admin_compliance,
    admin_channels,
    audience,
    segments,
    templates,
    campaigns,
    content,
    content_quality,
    distribution,
    webhooks,
    notifications,
    messages,
    feedback,
    link_tracking,
    analytics,
)
from app.db.session import SessionLocal
from app.db.seed import seed_default_roles
from app.services.scheduler_service import start_scheduler, shutdown_scheduler

logging.basicConfig(
    level=logging.INFO if not settings.DEBUG else logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = setup_pii_redacting_logger("masscommai")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup and shutdown procedures."""
    logger.info("Initializing %s v%s in %s environment...", settings.PROJECT_NAME, settings.VERSION, settings.APP_ENV)
    # Ensure default roles exist on startup
    try:
        with SessionLocal() as db:
            seed_default_roles(db)
            logger.info("Default system roles verified during application startup.")
    except Exception as exc:
        logger.warning("Startup role seeding could not complete: %s", exc)

    # Initialize and start APScheduler AsyncIOScheduler
    try:
        start_scheduler()
    except Exception as exc:
        logger.warning("APScheduler startup encountered error: %s", exc)

    yield

    logger.info("Shutting down %s...", settings.PROJECT_NAME)
    try:
        shutdown_scheduler()
    except Exception as exc:
        logger.warning("APScheduler shutdown encountered error: %s", exc)


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Backend API for AI-Powered Multilingual Public Awareness and Mass Communication Platform",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# Configure CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def global_unhandled_exception_handler(request: Request, exc: Exception):
    """
    Global exception handler preventing stack traces or internal implementation details
    from leaking to API clients while ensuring safe redacting server logs.
    """
    if isinstance(exc, StarletteHTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
            headers=getattr(exc, "headers", None),
        )
    if isinstance(exc, RequestValidationError):
        return JSONResponse(
            status_code=422,
            content={"detail": exc.errors()},
        )
    logger.exception("Unhandled server exception processing %s %s: %s", request.method, request.url.path, exc)
    return JSONResponse(
        status_code=500,
        content={
            "detail": "An internal server error occurred. Please contact the system administrator.",
            "error_code": "INTERNAL_SERVER_ERROR",
        },
    )

# Register Routers
app.include_router(health.router)
app.include_router(auth.router)
app.include_router(admin_users.router)
app.include_router(admin_compliance.router)
app.include_router(admin_channels.router)
app.include_router(audience.router)
app.include_router(segments.router)
app.include_router(templates.router)
app.include_router(campaigns.router)
app.include_router(content.router)
app.include_router(content_quality.router)
app.include_router(distribution.router)
app.include_router(webhooks.router)
app.include_router(notifications.router)
app.include_router(messages.router)
app.include_router(feedback.router)
app.include_router(link_tracking.router)
app.include_router(analytics.router)


@app.get("/", tags=["Root"])
def root():
    """Root welcome endpoint providing platform metadata and navigation links."""
    return {
        "title": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "status": "operational",
        "docs_url": "/docs",
        "health_check_url": "/health",
        "register_url": "/auth/register",
    }
