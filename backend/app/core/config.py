from functools import lru_cache
from typing import List, Optional
from pydantic import computed_field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    PROJECT_NAME: str = "Civora"
    VERSION: str = "1.0.0"
    APP_ENV: str = "development"
    DEBUG: bool = True

    # Database
    DATABASE_URL: str = "postgresql+psycopg://postgres:postgres@localhost:5432/masscommai_dev"

    # Security
    SECRET_KEY: str = "replace-with-a-secure-random-secret-key-at-least-32-chars-long"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    # CORS
    CORS_ORIGINS: str = "http://127.0.0.1:5173,http://localhost:5173"

    # Redis & Distributed Rate Limiting
    REDIS_URL: Optional[str] = None
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_LOGIN_PER_MINUTE: int = 10
    RATE_LIMIT_AI_PER_MINUTE: int = 20

    # AI Generation & Translation — Groq (primary) / Gemini (legacy) / Mock (fallback)
    # Groq
    GROQ_API_KEY: Optional[str] = None
    GROQ_MODEL: str = "openai/gpt-oss-120b"
    # Gemini (legacy; kept for backward compatibility)
    GEMINI_API_KEY: Optional[str] = None
    # Provider selection: "auto" (Groq→Gemini→Mock), "groq", "gemini", "mock"
    AI_PROVIDER: str = "auto"
    # Fallback model name used by GeminiAIProvider when AI_MODEL_NAME is set
    AI_MODEL_NAME: str = "gemini-2.5-flash"
    # Shared retry/timeout settings
    AI_REQUEST_TIMEOUT_SECONDS: float = 30.0
    AI_MAX_RETRIES: int = 2
    AI_INITIAL_BACKOFF_SECONDS: float = 1.0
    AI_MAX_BACKOFF_SECONDS: float = 8.0
    AI_OVERALL_DEADLINE_SECONDS: float = 30.0

    # Channel Constraints & Policy Thresholds
    SMS_HARD_LIMIT_CHARS: int = 1600
    SMS_MAX_RECOMMENDED_SEGMENTS: int = 3
    VOICE_MAX_RECOMMENDED_SECONDS: int = 90
    WHATSAPP_FREEFORM_HARD_LIMIT_CHARS: int = 4096
    WHATSAPP_RECOMMENDED_LIMIT_CHARS: int = 1024
    WHATSAPP_TEMPLATE_LIMIT_CHARS: int = 1024
    EMAIL_SUBJECT_RECOMMENDED_LIMIT_CHARS: int = 78
    EMAIL_BODY_RECOMMENDED_WORDS: int = 800

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def normalize_database_url(cls, v: Optional[str]) -> str:
        """
        Normalize cloud PostgreSQL URLs for compatibility with psycopg v3.
        Handles standard formats:
        - postgres://... -> postgresql+psycopg://...
        - postgresql://... -> postgresql+psycopg://...
        - postgresql+psycopg://... -> unchanged (avoids double prefixing)
        - Preserves sqlite:// and other explicit drivers untouched.
        """
        if not v:
            return "postgresql+psycopg://postgres:postgres@localhost:5432/masscommai_dev"
        url = v.strip()
        if url.startswith("postgresql+"):
            return url
        if url.startswith("postgres://"):
            return "postgresql+psycopg://" + url[len("postgres://"):]
        if url.startswith("postgresql://"):
            return "postgresql+psycopg://" + url[len("postgresql://"):]
        return url

    @field_validator("REDIS_URL", mode="before")
    @classmethod
    def normalize_redis_url(cls, v: Optional[str]) -> Optional[str]:
        """Convert empty string or whitespace REDIS_URL to None to activate in-memory fallback."""
        if v is None:
            return None
        v = v.strip()
        return v if v else None

    @model_validator(mode="after")
    def validate_production_security(self) -> "Settings":
        """
        Validate security settings based on APP_ENV.
        In production/staging:
        - SECRET_KEY must be set, must not be a known default placeholder, and must be >= 32 chars.
        In development/testing:
        - SECRET_KEY must be non-empty (defaults to development placeholder if unset).
        """
        env = self.APP_ENV.lower().strip()
        insecure_placeholders = {
            "replace-with-a-secure-random-secret-key",
            "replace-with-a-secure-random-secret-key-at-least-32-chars-long",
            "changeme",
            "secret",
            "password",
            "default",
        }
        secret = self.SECRET_KEY.strip() if self.SECRET_KEY else ""

        if not secret:
            raise ValueError("SECRET_KEY must not be empty.")

        if env in ("production", "prod", "staging"):
            if secret in insecure_placeholders:
                raise ValueError(
                    f"In {self.APP_ENV} environment, SECRET_KEY cannot be a default placeholder. "
                    "Set a cryptographically strong random secret key (min 32 characters)."
                )
            if len(secret) < 32:
                raise ValueError(
                    f"In {self.APP_ENV} environment, SECRET_KEY must be at least 32 characters long."
                )
            if "*" in self.cors_origins_list:
                raise ValueError(
                    f"In {self.APP_ENV} environment, wildcard '*' is forbidden in CORS_ORIGINS."
                )

        return self

    @computed_field
    @property
    def cors_origins_list(self) -> List[str]:
        """Convert comma-separated CORS_ORIGINS string into a list of origins, stripping trailing slashes."""
        if not self.CORS_ORIGINS:
            return ["http://127.0.0.1:5173", "http://localhost:5173"]
        origins = []
        for origin in self.CORS_ORIGINS.split(","):
            cleaned = origin.strip().rstrip("/")
            if cleaned:
                origins.append(cleaned)
        return origins or ["http://127.0.0.1:5173", "http://localhost:5173"]

    model_config = SettingsConfigDict(
        env_file=("backend/.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache()
def get_settings() -> Settings:
    """Return cached instance of application settings."""
    return Settings()


settings = get_settings()

