from __future__ import annotations
import uuid
from typing import TYPE_CHECKING, Optional, List, Dict, Any
from datetime import datetime
from sqlalchemy import String, Integer, Boolean, ForeignKey, DateTime, func, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

if TYPE_CHECKING:
    from app.models.campaign import Campaign
    from app.models.communication import Message
    from app.models.audience import AudienceMember


class TrackedLink(Base):
    """
    Tracked outbound hyperlink embedded in distributed campaign communications.
    Enables click tracking, redirection attribution, and open-redirect vulnerability prevention.
    """

    __tablename__ = "tracked_links"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    link_id: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        nullable=False,
        index=True,
        default=lambda: f"lnk_{uuid.uuid4().hex[:12]}",
        comment="Short public alphanumeric identifier for the redirect URL",
    )
    campaign_id: Mapped[int] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Associated campaign",
    )
    message_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("messages.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        comment="Optional specific outbound message containing this link",
    )
    original_url: Mapped[str] = mapped_column(
        String(2048),
        nullable=False,
        comment="Original destination URL validated against allowed schemes",
    )
    click_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Total recorded recipient click interactions",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
        comment="Whether link redirection is currently active",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    last_clicked_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp of the most recent click",
    )

    # Relationships
    campaign: Mapped[Campaign] = relationship("Campaign", back_populates="tracked_links")
    message: Mapped[Optional[Message]] = relationship("Message", back_populates="tracked_links")


class EngagementEvent(Base):
    """
    Persistent audit record of an audience member engagement action
    (email open, link click, inbound reply, feedback participation).
    """

    __tablename__ = "engagement_events"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    campaign_id: Mapped[int] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Associated campaign",
    )
    message_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("messages.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        comment="Associated message if event was triggered from a specific dispatch",
    )
    audience_member_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("audience_members.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Associated recipient citizen",
    )
    event_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        index=True,
        comment="Type of engagement: open, click, reply, participate",
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
        comment="UTC timestamp when interaction occurred",
    )
    device_info: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Cleaned client device or User-Agent classification (e.g., Mobile, Desktop)",
    )
    language: Mapped[Optional[str]] = mapped_column(
        String(30),
        nullable=True,
        default="en",
        comment="Language of the interaction",
    )
    link_url: Mapped[Optional[str]] = mapped_column(
        String(1000),
        nullable=True,
        comment="Target URL clicked for click events",
    )
    metadata_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"),
        nullable=True,
        default=dict,
        comment="Extensible event metadata e.g. feedback rating, reply snippet, provider ID",
    )

    # Relationships
    campaign: Mapped[Campaign] = relationship("Campaign", back_populates="engagement_events")
    message: Mapped[Optional[Message]] = relationship("Message", back_populates="engagement_events")
    audience_member: Mapped[Optional[AudienceMember]] = relationship("AudienceMember", back_populates="engagement_events")
