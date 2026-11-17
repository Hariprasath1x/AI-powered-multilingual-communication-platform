"""SQLAlchemy ORM model for public web announcements and real-time broadcasts."""

from __future__ import annotations
from typing import TYPE_CHECKING, Optional, List, Dict, Any
from datetime import datetime
from sqlalchemy import String, Text, Boolean, Integer, ForeignKey, DateTime, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.campaign import Campaign


class WebBroadcast(Base, TimestampMixin):
    """
    Public web announcement and citizen broadcast record.
    Preserves anonymity: broadcasts transmit campaign content to connected citizen clients
    via WebSockets and Server-Sent Events (SSE) without exposing any recipient PII.
    """

    __tablename__ = "web_broadcasts"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    campaign_id: Mapped[int] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Public announcement headline",
    )
    body: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Rendered multilingual body text of the broadcast",
    )
    language: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="en",
        index=True,
    )
    is_emergency: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
        comment="Emergency broadcast flag triggering high-priority citizen alerts",
    )
    priority: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="normal",
        comment="Priority rating: normal, urgent, emergency",
    )
    channels_dispatched: Mapped[Optional[List[str]]] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"),
        nullable=True,
        default=list,
        comment="Transport protocols used: websocket, sse, public_web",
    )
    connected_clients_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of active citizen browser listeners connected at dispatch time",
    )
    broadcast_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    # Relationships
    campaign: Mapped[Campaign] = relationship("Campaign")
