from __future__ import annotations
import uuid
from typing import TYPE_CHECKING, List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy import String, Text, Integer, Float, ForeignKey, DateTime, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

if TYPE_CHECKING:
    from app.models.campaign import Campaign
    from app.models.audience import AudienceMember
    from app.models.template import Template
    from app.models.content_asset import ContentAsset
    from app.models.content_variant import ContentVariant


class Message(Base):
    """Generated or queued outgoing communication message dispatched to an audience member."""

    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    tracking_id: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        nullable=False,
        index=True,
        default=lambda: f"trk_{uuid.uuid4().hex}",
        comment="Unique public tracking identifier for delivery status and engagement metrics",
    )
    campaign_id: Mapped[int] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    audience_member_id: Mapped[int] = mapped_column(
        ForeignKey("audience_members.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    template_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("templates.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    content_asset_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("content_assets.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    content_variant_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("content_variants.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    channel: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    language: Mapped[str] = mapped_column(String(30), nullable=False, default="en")
    rendered_content: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="Queued",
        index=True,
        comment="Queued, Sent, Delivered, Failed",
    )
    provider_message_id: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        index=True,
        comment="Gateway or provider-assigned message tracking identifier",
    )
    failure_reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Standardized failure reason or provider diagnostic message",
    )
    fallback_attempts: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"),
        nullable=True,
        default=list,
        comment="Recorded delivery attempts across fallback channels before success or terminal failure",
    )
    scheduled_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    sent_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    delivered_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    campaign: Mapped[Campaign] = relationship(back_populates="messages")
    audience_member: Mapped[AudienceMember] = relationship(back_populates="messages")
    template: Mapped[Optional[Template]] = relationship(back_populates="messages")
    content_asset: Mapped[Optional[ContentAsset]] = relationship("ContentAsset")
    content_variant: Mapped[Optional[ContentVariant]] = relationship("ContentVariant")
    delivery_logs: Mapped[List[DeliveryLog]] = relationship(
        back_populates="message",
        cascade="all, delete-orphan",
    )


class DeliveryLog(Base):
    """Audit log tracking delivery outcomes, provider responses, and retry attempts."""

    __tablename__ = "delivery_logs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    message_id: Mapped[int] = mapped_column(
        ForeignKey("messages.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    channel: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        index=True,
        comment="Sent, Delivered, Failed",
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    message: Mapped[Message] = relationship(back_populates="delivery_logs")


class Feedback(Base):
    """Recipient engagement and response feedback collection."""

    __tablename__ = "feedback"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    campaign_id: Mapped[int] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    audience_member_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("audience_members.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    rating: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, comment="1 to 5 stars")
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Forward-compatible sentiment analysis fields (Milestone 3)
    sentiment_label: Mapped[Optional[str]] = mapped_column(
        String(30),
        nullable=True,
        comment="Positive, Neutral, Negative",
    )
    sentiment_score: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Sentiment confidence or polarity score (-1.0 to 1.0)",
    )
    language: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    campaign: Mapped[Campaign] = relationship(back_populates="feedbacks")
    audience_member: Mapped[Optional[AudienceMember]] = relationship(back_populates="feedbacks")

