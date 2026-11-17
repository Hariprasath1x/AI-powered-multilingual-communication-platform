from __future__ import annotations
from typing import TYPE_CHECKING, Optional, List, Dict, Any
from datetime import datetime
from sqlalchemy import String, Text, Integer, Boolean, ForeignKey, DateTime, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.campaign import Campaign
    from app.models.communication import Message
    from app.models.audience import AudienceMember


class AutomationRule(Base, TimestampMixin):
    """
    Configurable automated workflow rule for campaigns.
    Example: IF a message is not opened within 24 hours, THEN send a reminder through SMS.
    """

    __tablename__ = "automation_rules"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    campaign_id: Mapped[int] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    trigger_condition: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="message_not_opened",
        index=True,
        comment="Condition: message_not_opened, message_delivery_failed, message_not_delivered",
    )
    wait_hours: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=24,
        comment="Waiting period in hours before trigger fires (e.g. 24 hours without an open event)",
    )
    wait_minutes: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        default=None,
        comment="Optional granular waiting period in minutes for test simulation",
    )
    action_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="send_reminder",
        comment="Action: send_reminder, send_fallback, notify_admin",
    )
    action_channel: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="SMS",
        comment="Target channel to dispatch reminder: SMS, Email, WhatsApp, Push",
    )
    custom_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Optional override text for the automated reminder message",
    )
    is_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
    )

    # Relationships
    campaign: Mapped[Campaign] = relationship("Campaign", back_populates="automation_rules")
    execution_logs: Mapped[List[AutomationExecutionLog]] = relationship(
        "AutomationExecutionLog",
        back_populates="rule",
        cascade="all, delete-orphan",
    )


class AutomationExecutionLog(Base):
    """
    Audit and deduplication record for automated workflow actions.
    Guarantees no rule is ever executed repeatedly for the same message (prevents infinite loops).
    """

    __tablename__ = "automation_execution_logs"
    __table_args__ = (
        UniqueConstraint("rule_id", "message_id", name="uq_automation_rule_message"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    rule_id: Mapped[int] = mapped_column(
        ForeignKey("automation_rules.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    campaign_id: Mapped[int] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    message_id: Mapped[int] = mapped_column(
        ForeignKey("messages.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    audience_member_id: Mapped[int] = mapped_column(
        ForeignKey("audience_members.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    action_taken: Mapped[str] = mapped_column(String(100), nullable=False)
    target_channel: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="success",
        comment="Execution outcome: success, skipped, failed",
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    executed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    # Relationships
    rule: Mapped[AutomationRule] = relationship("AutomationRule", back_populates="execution_logs")
    campaign: Mapped[Campaign] = relationship("Campaign", back_populates="automation_logs")
    message: Mapped[Message] = relationship("Message")
    audience_member: Mapped[AudienceMember] = relationship("AudienceMember")
