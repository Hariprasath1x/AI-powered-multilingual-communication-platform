"""API Routers package."""

from app.routers import health, auth, admin_users, audience, segments, templates, campaigns, content, content_quality, distribution, admin_compliance

__all__ = [
    "health",
    "auth",
    "admin_users",
    "audience",
    "segments",
    "templates",
    "campaigns",
    "content",
    "content_quality",
    "distribution",
    "admin_compliance",
]
