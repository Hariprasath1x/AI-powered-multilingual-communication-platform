"""SQLAlchemy ORM model for citizen and device registration tokens (FCM/APNs/Web Push)."""

from __future__ import annotations
from typing import TYPE_CHECKING, Optional, Dict, Any
from datetime import datetime
from sqlalchemy import String, Boolean, Integer, ForeignKey, DateTime, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.audience import AudienceMember
    from app.models.user import User


class DeviceToken(Base, TimestampMixin):
    """
    Push notification destination token registered by a citizen browser or mobile client.
    Tracks device platform, active state, and automated invalidation upon gateway token expiry.
    """

    __tablename__ = "device_tokens"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    token: Mapped[str] = mapped_column(
        String(500),
        unique=True,
        nullable=False,
        index=True,
        comment="FCM registration token, Web Push subscription endpoint, or APNs hex token",
    )
    audience_member_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("audience_members.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        comment="Associated AudienceMember profile if citizen is identified",
    )
    user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        comment="Associated platform User if user is authenticated",
    )
    device_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="web",
        index=True,
        comment="web, android, ios",
    )
    platform_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"),
        nullable=True,
        default=dict,
        comment="Browser user-agent, operating system, app build, or push endpoint details",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
        comment="False when token is revoked, unregistered, or reported expired by FCM",
    )
    last_used_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp of latest successful dispatch to this device",
    )

    # Relationships
    audience_member: Mapped[Optional[AudienceMember]] = relationship("AudienceMember", backref="device_tokens")
    user: Mapped[Optional[User]] = relationship("User", backref="device_tokens")
