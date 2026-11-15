"""SQLAlchemy ORM models for Multichannel Distribution Jobs, Delivery Records, and Attempts."""

from __future__ import annotations
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional, Any
from sqlalchemy import String, Text, Integer, ForeignKey, DateTime, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.campaign import Campaign
    from app.models.audience import AudienceMember
    from app.models.template import Template
    from app.models.content_asset import ContentAsset


class DistributionJob(Base, TimestampMixin):
    """
    Persistent distribution operation record for a campaign across a target channel.
    Manages batch lifecycle state, aggregate recipient counters, and execution progress.
    """

    __tablename__ = "distribution_jobs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    job_id: Mapped[str] = mapped_column(
        String(36),
        unique=True,
        nullable=False,
        index=True,
        default=lambda: str(uuid.uuid4()),
        comment="Public UUID identifier for API consumers",
    )
    campaign_id: Mapped[int] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    content_asset_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("content_assets.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    template_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("templates.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    channel: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        index=True,
        comment="Email, SMS, WhatsApp, Voice, Web",
    )
    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="pending",
        index=True,
        comment="pending, queued, processing, completed, completed_with_errors, failed, cancelled",
    )

    # Aggregate recipient counters
    total_recipients: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    eligible_recipients: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    queued_recipients: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sent_recipients: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    delivered_recipients: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_recipients: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    skipped_recipients: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    error_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Worker lease and stale recovery tracking
    locked_by: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Worker process identifier holding the active processing lease",
    )
    locked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    lease_expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        comment="Timestamp when the worker lease expires if not refreshed by heartbeat",
    )
    last_heartbeat_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    recovery_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Count of automated stale processing recovery events",
    )

    created_by: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    # Relationships
    campaign: Mapped[Campaign] = relationship("Campaign", back_populates="distribution_jobs")
    content_asset: Mapped[Optional[ContentAsset]] = relationship("ContentAsset")
    template: Mapped[Optional[Template]] = relationship("Template")
    creator: Mapped[User] = relationship("User")
    delivery_records: Mapped[List[DeliveryRecord]] = relationship(
        "DeliveryRecord",
        back_populates="job",
        cascade="all, delete-orphan",
        order_by="DeliveryRecord.id",
    )


class DeliveryRecord(Base, TimestampMixin):
    """
    Individual recipient delivery record tracking personalized dispatch,
    status transitions, attempt counts, provider references, and errors.
    """

    __tablename__ = "delivery_records"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    delivery_id: Mapped[str] = mapped_column(
        String(36),
        unique=True,
        nullable=False,
        index=True,
        default=lambda: str(uuid.uuid4()),
    )
    job_id: Mapped[int] = mapped_column(
        ForeignKey("distribution_jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    audience_member_id: Mapped[int] = mapped_column(
        ForeignKey("audience_members.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    channel: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    recipient_address: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Sanitized destination (email, phone, or account identifier)",
    )
    rendered_content: Mapped[str] = mapped_column(Text, nullable=False)
    delivery_status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="pending",
        index=True,
        comment="pending, processing, sent, delivered, failed, retrying, cancelled, skipped_consent",
    )
    provider_name: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    provider_reference: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    last_attempt_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    next_retry_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        comment="Scheduled timestamp for next bounded backoff retry attempt",
    )
    delivered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    error_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    idempotency_key: Mapped[str] = mapped_column(
        String(128),
        unique=True,
        nullable=False,
        index=True,
        comment="Unique key ensuring at-most-once delivery per recipient and job",
    )

    # Relationships
    job: Mapped[DistributionJob] = relationship("DistributionJob", back_populates="delivery_records")
    audience_member: Mapped[AudienceMember] = relationship("AudienceMember")
    attempts: Mapped[List[DeliveryAttempt]] = relationship(
        "DeliveryAttempt",
        back_populates="delivery_record",
        cascade="all, delete-orphan",
        order_by="DeliveryAttempt.attempt_number",
    )

    __table_args__ = (
        UniqueConstraint("job_id", "audience_member_id", "channel", name="uq_job_recipient_channel"),
    )


class DeliveryAttempt(Base):
    """
    Granular attempt log recording each individual execution, simulated provider
    response, latency, and failure classification.
    """

    __tablename__ = "delivery_attempts"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    delivery_record_id: Mapped[int] = mapped_column(
        ForeignKey("delivery_records.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    provider_name: Mapped[str] = mapped_column(String(50), nullable=False)
    attempt_status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        comment="success, failure, timeout, skipped",
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    error_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    response_metadata: Mapped[Optional[Any]] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"),
        nullable=True,
        default=dict,
    )

    # Relationships
    delivery_record: Mapped[DeliveryRecord] = relationship("DeliveryRecord", back_populates="attempts")

