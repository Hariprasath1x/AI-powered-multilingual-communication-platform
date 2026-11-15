"""SQLAlchemy model for audience demographic content variants (Milestone 2, Task 9.A)."""

from __future__ import annotations
from typing import TYPE_CHECKING, Optional
from datetime import datetime
from sqlalchemy import String, Text, ForeignKey, DateTime, Index, func, text, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.campaign import Campaign
    from app.models.content_asset import ContentAsset
    from app.models.segment import Segment
    from app.models.content_quality import ContentQualityAssessment


class ContentVariant(Base, TimestampMixin):
    """
    Audience-specific personalized content variant tailored for a demographic segment.
    Maintains foreign-key lineage to the source content asset, campaign, and target segment.
    Carries its own review lifecycle and quality assessment verification.
    """

    __tablename__ = "content_variants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # Core Foreign Key Lineage
    campaign_id: Mapped[int] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_content_id: Mapped[int] = mapped_column(
        ForeignKey("content_assets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    segment_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("segments.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Content Attributes
    language: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="en",
        index=True,
    )
    channel: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="Email",
        index=True,
    )
    variant_title: Mapped[str] = mapped_column(String(255), nullable=False)
    variant_body: Mapped[str] = mapped_column(Text, nullable=False)
    variant_cta: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    personalization_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Editorial Review & Lifecycle (Draft -> In_Review -> Approved / Rejected)
    review_status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="Draft",
        index=True,
        comment="Draft, In_Review, Approved, Rejected",
    )
    review_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reviewed_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Quality Assessment & Content Freshness Verification
    assessment_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("content_quality_assessments.id", ondelete="SET NULL"),
        nullable=True,
    )
    content_version_hash: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
        comment="SHA-256 hash of title+body+cta at time of assessment",
    )

    # Authorship
    created_by: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    # Relationships
    campaign: Mapped[Campaign] = relationship(
        "Campaign",
        foreign_keys=[campaign_id],
    )
    source_content: Mapped[ContentAsset] = relationship(
        "ContentAsset",
        foreign_keys=[source_content_id],
    )
    segment: Mapped[Optional[Segment]] = relationship(
        "Segment",
        foreign_keys=[segment_id],
    )
    creator: Mapped[User] = relationship(
        "User",
        foreign_keys=[created_by],
    )
    reviewer: Mapped[Optional[User]] = relationship(
        "User",
        foreign_keys=[reviewed_by],
    )
    assessment: Mapped[Optional[ContentQualityAssessment]] = relationship(
        "ContentQualityAssessment",
        foreign_keys=[assessment_id],
    )

    __table_args__ = (
        # Functional unique index enforcing uniqueness for (source_content_id, segment_id, lower(language))
        Index(
            "uq_content_variant_source_segment_lang",
            "source_content_id",
            "segment_id",
            func.lower(language),
            unique=True,
            postgresql_where=text("segment_id IS NOT NULL"),
            sqlite_where=text("segment_id IS NOT NULL"),
        ),
        # Fallback unique index when segment_id IS NULL
        Index(
            "uq_content_variant_source_lang_no_segment",
            "source_content_id",
            func.lower(language),
            unique=True,
            postgresql_where=text("segment_id IS NULL"),
            sqlite_where=text("segment_id IS NULL"),
        ),
    )

