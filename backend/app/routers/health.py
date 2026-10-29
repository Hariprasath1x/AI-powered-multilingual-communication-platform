import logging
from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from app.core.config import settings
from app.db.session import get_db

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    summary="Health Check",
    description="Validates API runtime health and active database connectivity via a lightweight query.",
    responses={
        200: {
            "description": "System and database are healthy.",
            "content": {
                "application/json": {
                    "example": {
                        "status": "healthy",
                        "database": "connected",
                        "version": "1.0.0",
                    }
                }
            },
        },
        503: {
            "description": "Database or core service is degraded.",
            "content": {
                "application/json": {
                    "example": {
                        "status": "degraded",
                        "database": "disconnected",
                        "version": "1.0.0",
                    }
                }
            },
        },
    },
)
def check_health(db: Session = Depends(get_db)):
    """Health-check endpoint validating server runtime and live database connectivity."""
    try:
        # Perform lightweight connectivity probe without exposing DB metadata
        result = db.execute(text("SELECT 1")).scalar()
        if result == 1:
            return {
                "status": "healthy",
                "database": "connected",
                "version": settings.VERSION,
            }
        else:
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={
                    "status": "degraded",
                    "database": "unexpected_result",
                    "version": settings.VERSION,
                },
            )
    except SQLAlchemyError as exc:
        logger.error("Health check database probe failed: %s", exc.__class__.__name__)
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "degraded",
                "database": "disconnected",
                "version": settings.VERSION,
            },
        )
    except Exception as exc:
        logger.error("Health check encountered unhandled error: %s", exc.__class__.__name__)
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "degraded",
                "database": "unavailable",
                "version": settings.VERSION,
            },
        )
