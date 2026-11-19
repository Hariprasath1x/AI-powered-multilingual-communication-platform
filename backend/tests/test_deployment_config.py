"""
Tests for deployment readiness and configuration normalization.

Validates:
1. PostgreSQL URL driver normalization for psycopg v3 (postgres://, postgresql://, postgresql+psycopg://).
2. Preservation of non-Postgres URLs (sqlite://, postgresql+asyncpg://).
3. Redis URL normalization (empty string/whitespace -> None, rediss:// TLS preserved).
4. CORS origin parsing and trailing slash stripping.
5. Production security validation for SECRET_KEY and CORS wildcards.
"""

import pytest
from app.core.config import Settings


def test_database_url_normalization_postgres_prefix():
    """Verify postgres:// is converted to postgresql+psycopg://."""
    s = Settings(
        DATABASE_URL="postgres://user:secret123@ep-sample-123.neon.tech/neondb?sslmode=require",
        APP_ENV="development",
    )
    assert s.DATABASE_URL == "postgresql+psycopg://user:secret123@ep-sample-123.neon.tech/neondb?sslmode=require"


def test_database_url_normalization_postgresql_prefix():
    """Verify postgresql:// is converted to postgresql+psycopg://."""
    s = Settings(
        DATABASE_URL="postgresql://neonuser:pword@ep-cold-lake.us-east-2.aws.neon.tech/masscomm",
        APP_ENV="development",
    )
    assert s.DATABASE_URL == "postgresql+psycopg://neonuser:pword@ep-cold-lake.us-east-2.aws.neon.tech/masscomm"


def test_database_url_normalization_already_correct():
    """Verify postgresql+psycopg:// is not double-prefixed."""
    original = "postgresql+psycopg://postgres:postgres@localhost:5432/masscommai_dev"
    s = Settings(DATABASE_URL=original, APP_ENV="development")
    assert s.DATABASE_URL == original


def test_database_url_normalization_sqlite_preserved():
    """Verify sqlite:// URLs are preserved as-is for test harnesses."""
    s = Settings(DATABASE_URL="sqlite:///./test.db", APP_ENV="development")
    assert s.DATABASE_URL == "sqlite:///./test.db"


def test_redis_url_normalization():
    """Verify empty or whitespace REDIS_URL resolves to None."""
    s_empty = Settings(REDIS_URL="", APP_ENV="development")
    assert s_empty.REDIS_URL is None

    s_whitespace = Settings(REDIS_URL="   ", APP_ENV="development")
    assert s_whitespace.REDIS_URL is None

    # Upstash TLS URL preserved
    upstash_url = "rediss://default:token_abc123@us1-quick-frog-12345.upstash.io:6379"
    s_tls = Settings(REDIS_URL=upstash_url, APP_ENV="development")
    assert s_tls.REDIS_URL == upstash_url


def test_cors_origins_list_trailing_slash_stripped():
    """Verify trailing slashes on frontend origins are stripped to prevent CORS preflight failures."""
    s = Settings(
        CORS_ORIGINS="https://masscommai.vercel.app/, http://localhost:5173/ , https://preview-123.vercel.app",
        APP_ENV="development",
    )
    assert s.cors_origins_list == [
        "https://masscommai.vercel.app",
        "http://localhost:5173",
        "https://preview-123.vercel.app",
    ]


def test_production_cors_wildcard_rejected():
    """Verify wildcard CORS origin is rejected in production."""
    with pytest.raises(ValueError, match="wildcard '\\*' is forbidden"):
        Settings(
            APP_ENV="production",
            SECRET_KEY="a" * 32,
            CORS_ORIGINS="*",
        )


def test_production_secret_key_validation():
    """Verify default placeholder secret keys are rejected in production."""
    with pytest.raises(ValueError, match="SECRET_KEY cannot be a default placeholder"):
        Settings(
            APP_ENV="production",
            SECRET_KEY="replace-with-a-secure-random-secret-key-at-least-32-chars-long",
            CORS_ORIGINS="https://masscommai.vercel.app",
        )

