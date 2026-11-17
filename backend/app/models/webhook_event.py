"""SQLAlchemy ORM model for inbound webhook deduplication and event auditing."""

from __future__ import annotations
from typing import Optional, Dict, Any
from datetime import datetime
from sqlalchemy import String, Text, DateTime, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import JSON
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base, TimestampMixin


class WebhookEvent(Base, TimestampMixin):
    """
    Idempotent event log for inbound provider webhooks (Meta WhatsApp, Firebase FCM).
    Ensures duplicate webhook payloads are rejected and delivery receipt events are auditable.
    """

    __tablename__ = "webhook_events"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    provider: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Provider source identifier: whatsapp, fcm, twilio",
    )
    event_id: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
        comment="Unique provider event or notification identifier for deduplication",
    )
    event_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="Event type: message_status, delivery_receipt, inbound_message",
    )
    payload: Mapped[Dict[str, Any]] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"),
        nullable=False,
        comment="Raw verified webhook payload",
    )
    processed_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="received",
        index=True,
        comment="Processing outcome: received, processed, ignored, failed",
    )
    error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Diagnostic error details if webhook handling encountered an error",
    )
