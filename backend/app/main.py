import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.routers import health, auth
from app.db.session import SessionLocal
from app.db.seed import seed_default_roles

logging.basicConfig(
    level=logging.INFO if not settings.DEBUG else logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("masscommai")


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

    yield
    logger.info("Shutting down %s...", settings.PROJECT_NAME)


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

# Register Routers
app.include_router(health.router)
app.include_router(auth.router)


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
