from __future__ import annotations
from typing import TYPE_CHECKING, List, Optional, Any
from datetime import datetime
from sqlalchemy import String, Text, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.segment import Segment
    from app.models.template import Template
    from app.models.communication import Message, Feedback
    from app.models.content_asset import ContentAsset


class Campaign(Base, TimestampMixin):
    """Campaign entity orchestrating audience targeting, content generation, and distribution."""

    __tablename__ = "campaigns"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    campaign_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Awareness, Emergency Alert, Educational, Organizational Announcement",
    )
    objective: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    priority: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="Medium",
        index=True,
        comment="Low, Medium, High",
    )
    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="Draft",
        index=True,
        comment="Draft, In Review, Approved, Scheduled, Running, Completed, Failed",
    )
    channels: Mapped[List[Any]] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"),
        nullable=False,
        default=list,
        comment="List of selected distribution channels e.g. ['Email', 'SMS']",
    )
    start_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    end_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    template_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("templates.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_by: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    # Relationships
    creator: Mapped[User] = relationship(back_populates="created_campaigns")
    template: Mapped[Optional[Template]] = relationship(back_populates="campaigns")
    segments: Mapped[List[Segment]] = relationship(
        secondary="campaign_segments",
        back_populates="campaigns",
    )
    messages: Mapped[List[Message]] = relationship(
        back_populates="campaign",
        cascade="all, delete-orphan",
    )
    feedbacks: Mapped[List[Feedback]] = relationship(
        back_populates="campaign",
        cascade="all, delete-orphan",
    )
    content_assets: Mapped[List[ContentAsset]] = relationship(
        "ContentAsset",
        back_populates="campaign",
    )

