from __future__ import annotations
from typing import TYPE_CHECKING, Optional, List, Dict, Any
from datetime import datetime
from sqlalchemy import String, Integer, Boolean, ForeignKey, DateTime, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.campaign import Campaign


class CampaignSchedule(Base, TimestampMixin):
    """
    Persistent schedule for an approved campaign.
    Supports one-time future broadcast, recurring daily/weekly schedules, and timezone offsets.
    """

    __tablename__ = "campaign_schedules"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    campaign_id: Mapped[int] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
        comment="Associated campaign to be distributed according to this schedule",
    )
    schedule_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="once",
        index=True,
        comment="Schedule type: once, daily, weekly",
    )
    scheduled_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        comment="Exact target UTC timestamp for one-time future broadcast",
    )
    recurrence_pattern: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="daily, weekly, or cron expression",
    )
    recurrence_time: Mapped[Optional[str]] = mapped_column(
        String(10),
        nullable=True,
        comment="HH:MM target execution time in the specified timezone e.g. '09:30'",
    )
    recurrence_days: Mapped[Optional[List[str]]] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"),
        nullable=True,
        default=list,
        comment="List of lowercase day abbreviations for weekly schedules e.g. ['mon', 'wed', 'fri']",
    )
    timezone: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="UTC",
        comment="IANA timezone identifier e.g. 'Asia/Kolkata', 'UTC', 'America/New_York'",
    )
    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="active",
        index=True,
        comment="Schedule status: active, paused, completed, cancelled",
    )
    last_run_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp when scheduler last triggered this campaign run",
    )
    next_run_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        comment="Computed next scheduled execution timestamp in UTC",
    )
    job_id: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        index=True,
        comment="Internal APScheduler job identifier",
    )
    execution_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Total number of times this schedule has triggered execution",
    )
    channels: Mapped[Optional[List[str]]] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"),
        nullable=True,
        default=list,
        comment="Target channels override for this schedule run",
    )
    fallback_order: Mapped[Optional[List[str]]] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"),
        nullable=True,
        default=list,
        comment="Configured multi-channel fallback chain",
    )
    enable_fallback: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Whether multi-channel fallback should be attempted on failure",
    )

    # Relationship
    campaign: Mapped[Campaign] = relationship("Campaign", back_populates="schedule")
