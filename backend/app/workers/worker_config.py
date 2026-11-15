"""Configuration settings for database-backed distribution queue worker."""

import os
import socket
import uuid
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def generate_default_worker_id() -> str:
    """Generates unique, traceable worker identifier incorporating host and PID."""
    host = socket.gethostname().split(".")[0]
    pid = os.getpid()
    unique = uuid.uuid4().hex[:8]
    return f"worker-{host}-{pid}-{unique}"


class WorkerConfig(BaseSettings):
    """
    Configuration parameters for independent distribution queue workers.
    Values can be overridden via environment variables prefixed with DISTRIBUTION_WORKER_.
    """

    worker_id: str = Field(default_factory=generate_default_worker_id)
    poll_interval: float = Field(default=2.0, ge=0.1, le=60.0, description="Seconds between queue polling iterations")
    batch_size: int = Field(default=50, ge=1, le=500, description="Max delivery records processed per batch")
    max_jobs_per_run: int = Field(default=10, ge=1, le=100, description="Max jobs claimed in one-shot run")
    lease_duration_seconds: int = Field(default=300, ge=30, le=3600, description="Worker lease duration in seconds")
    heartbeat_interval_seconds: int = Field(default=30, ge=5, le=300, description="Interval to update lease heartbeat")
    max_recoveries: int = Field(default=3, ge=1, le=10, description="Max automated stale recovery attempts per job")
    retry_backoff_base_seconds: int = Field(default=60, ge=5, le=600, description="Base seconds for exponential retry backoff")
    max_retry_backoff_seconds: int = Field(default=3600, ge=60, le=86400, description="Maximum backoff cap in seconds")

    model_config = SettingsConfigDict(
        env_prefix="DISTRIBUTION_WORKER_",
        env_file=("backend/.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

