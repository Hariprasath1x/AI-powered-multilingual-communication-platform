"""SQLAlchemy ORM models for Content Quality Assessments and Reviewer Findings."""

from __future__ import annotations
from typing import TYPE_CHECKING, List, Optional, Any
from datetime import datetime
from sqlalchemy import String, Text, Float, Integer, Boolean, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.content_asset import ContentAsset


class ContentQualityAssessment(Base, TimestampMixin):
    """
    Persistent record of a content quality, compliance, and editorial audit.
    Stores dimension-level scores, content version hash for staleness detection,
    and associated findings.
    """

    __tablename__ = "content_quality_assessments"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    content_asset_id: Mapped[int] = mapped_column(
        ForeignKey("content_assets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    content_version_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
        comment="SHA-256 hash of content title+body+cta to detect post-audit edits",
    )
    overall_score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="Overall quality score from 0.0 to 100.0",
    )
    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="completed",
        index=True,
        comment="completed, completed_with_warnings, failed, outdated",
    )
    dimension_scores: Mapped[Any] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"),
        nullable=False,
        default=dict,
        comment="JSON object storing language_grammar, readability, tone, translation, factual, channel",
    )
    evaluator_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="hybrid",
        comment="hybrid, deterministic, ai",
    )
    evaluator_metadata: Mapped[Optional[Any]] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"),
        nullable=True,
        default=dict,
    )
    critical_issues_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    high_issues_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    medium_issues_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    low_issues_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    info_issues_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    created_by: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    # Relationships
    content_asset: Mapped[ContentAsset] = relationship(
        "ContentAsset",
        back_populates="quality_assessments",
    )
    creator: Mapped[User] = relationship(
        "User",
        foreign_keys=[created_by],
    )
    findings: Mapped[List[ContentQualityFinding]] = relationship(
        "ContentQualityFinding",
        back_populates="assessment",
        cascade="all, delete-orphan",
        order_by="ContentQualityFinding.id",
    )


class ContentQualityFinding(Base, TimestampMixin):
    """
    Individual editorial finding generated during quality assessment.
    Maintains reviewer resolution status (accepted, rejected, corrected) and decision audit trail.
    """

    __tablename__ = "content_quality_findings"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    assessment_id: Mapped[int] = mapped_column(
        ForeignKey("content_quality_assessments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    category: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="grammar, readability, tone, translation, factual, channel, safety_sensitive, placeholder, completeness",
    )
    severity: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
        comment="critical, high, medium, low, informational",
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    affected_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    suggested_correction: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    evaluation_source: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="deterministic",
        comment="deterministic, ai",
    )
    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    rule_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Human Reviewer Decision
    reviewer_decision: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="pending",
        index=True,
        comment="pending, accepted, rejected, corrected",
    )
    decision_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    resolved_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    resolved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    assessment: Mapped[ContentQualityAssessment] = relationship(
        "ContentQualityAssessment",
        back_populates="findings",
    )
    resolver: Mapped[Optional[User]] = relationship(
        "User",
        foreign_keys=[resolved_by],
    )

