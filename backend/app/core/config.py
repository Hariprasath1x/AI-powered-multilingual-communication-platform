from functools import lru_cache
from typing import List
from pydantic import computed_field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    PROJECT_NAME: str = "MassCommAI"
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

        return self

    @computed_field
    @property
    def cors_origins_list(self) -> List[str]:
        """Convert comma-separated CORS_ORIGINS string into a list of origins."""
        if not self.CORS_ORIGINS:
            return ["http://127.0.0.1:5173", "http://localhost:5173"]
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

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

