"""SQLAlchemy ORM model for Administrator-Managed Dynamic Compliance Rules."""

from __future__ import annotations
from typing import TYPE_CHECKING, Optional
from datetime import datetime
from sqlalchemy import String, Text, Boolean, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User


class ComplianceRule(Base, TimestampMixin):
    """
    Persistent dynamic compliance rule configured by administrators.
    Supports banned vocabulary, mandatory phrases, and bounded regex patterns
    with organization scoping, channel/language filters, and severity levels.
    """

    __tablename__ = "compliance_rules"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    rule_code: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
        comment="Unique identifier for rule, e.g. COMP-BW-001",
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    rule_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        index=True,
        comment="banned_word, mandatory_phrase, regex_pattern",
    )
    pattern: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Prohibited word/phrase, required mandatory phrase, or safe regex",
    )
    severity: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="critical",
        index=True,
        comment="critical, high, medium, low, info",
    )
    organization: Mapped[Optional[str]] = mapped_column(
        String(150),
        nullable=True,
        index=True,
        comment="Target organization or department name; NULL indicates global applicability",
    )
    is_global: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        index=True,
        comment="If true, rule applies across all organizations regardless of organization column",
    )
    channel: Mapped[Optional[str]] = mapped_column(
        String(30),
        nullable=True,
        index=True,
        comment="Email, SMS, WhatsApp, Voice, or NULL for all channels",
    )
    language: Mapped[Optional[str]] = mapped_column(
        String(10),
        nullable=True,
        index=True,
        comment="Language code like 'en', 'hi', or NULL for all languages",
    )
    suggested_action: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Recommended guidance or replacement text for reviewers",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
        comment="Flag indicating if the rule is currently active in quality evaluation",
    )
    created_by: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    updated_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Relationships
    creator: Mapped[User] = relationship("User", foreign_keys=[created_by])
    updater: Mapped[Optional[User]] = relationship("User", foreign_keys=[updated_by])

    __table_args__ = (
        Index("ix_compliance_rules_org_active", "organization", "is_active"),
        Index("ix_compliance_rules_lookup", "is_active", "is_global", "rule_type"),
    )

