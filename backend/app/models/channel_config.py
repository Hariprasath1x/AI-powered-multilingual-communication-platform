"""SQLAlchemy ORM model for channel configurations and administrative settings."""

from __future__ import annotations
from typing import Optional, Dict, Any
from sqlalchemy import String, Boolean
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import JSON
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base, TimestampMixin


class ChannelConfiguration(Base, TimestampMixin):
    """
    Administrative channel configuration governing active provider adapter,
    enabled status, credentials, and sender metadata for a communication channel.
    """

    __tablename__ = "channel_configurations"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    channel: Mapped[str] = mapped_column(
        String(30),
        unique=True,
        nullable=False,
        index=True,
        comment="Email, SMS, WhatsApp, Voice, Web",
    )
    is_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Whether broadcasts over this channel are globally permitted",
    )
    provider_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="mock",
        comment="Active provider: mock, smtp, sendgrid, twilio, fast2sms",
    )
    sender_address: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="From email address, outbound phone number, or sender ID",
    )
    sender_name: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Display sender name or service label",
    )
    credentials: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"),
        nullable=True,
        default=dict,
        comment="Encrypted or masked provider API tokens, auth credentials, and host configs",
    )

