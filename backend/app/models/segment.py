from __future__ import annotations
from typing import TYPE_CHECKING, List, Optional, Any, Dict
from sqlalchemy import String, ForeignKey, Table, Column, Integer
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.campaign import Campaign

# Association Table for Campaigns and Segments (Many-to-Many)
campaign_segments = Table(
    "campaign_segments",
    Base.metadata,
    Column(
        "campaign_id",
        Integer,
        ForeignKey("campaigns.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "segment_id",
        Integer,
        ForeignKey("segments.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class Segment(Base, TimestampMixin):
    """Segment entity defining targeted audience rules using dynamic JSON criteria."""

    __tablename__ = "segments"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    filter_rules: Mapped[Dict[str, Any]] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"),
        nullable=False,
        default=dict,
    )
    created_by: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    # Relationships
    creator: Mapped[User] = relationship(back_populates="created_segments")
    campaigns: Mapped[List[Campaign]] = relationship(
        secondary=campaign_segments,
        back_populates="segments",
    )

