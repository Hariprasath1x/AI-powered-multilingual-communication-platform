"""SQLAlchemy ORM models for Multilingual Translation Caching and Review Audit History."""

from __future__ import annotations
from typing import TYPE_CHECKING, List, Optional, Any, Dict
from datetime import datetime
from sqlalchemy import String, Text, Integer, ForeignKey, DateTime, func, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.content_asset import ContentAsset


class TranslationCache(Base, TimestampMixin):
    """
    Persistent translation cache to avoid repeated LLM translation calls.
    Keyed deterministically on source text, title, CTA, source/target languages, and channel.
    """

    __tablename__ = "translation_cache"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    cache_key: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        index=True,
        nullable=False,
        comment="SHA-256 hash of source_lang:target_lang:channel:source_title:source_body:source_cta",
    )
    source_content_hash: Mapped[str] = mapped_column(
        String(64),
        index=True,
        nullable=False,
        comment="SHA-256 hash of source title+body+cta for quick invalidation on source content edits",
    )
    source_language: Mapped[str] = mapped_column(String(10), index=True, nullable=False)
    target_language: Mapped[str] = mapped_column(String(10), index=True, nullable=False)
    channel: Mapped[str] = mapped_column(String(30), nullable=False, default="Email")

    translated_title: Mapped[str] = mapped_column(String(255), nullable=False)
    translated_body: Mapped[str] = mapped_column(Text, nullable=False)
    translated_call_to_action: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    preserved_placeholders: Mapped[List[str]] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"),
        nullable=False,
        default=list,
        comment="List of preserved dynamic personalization tokens",
    )
    provider_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"),
        nullable=True,
        default=dict,
    )
    hit_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    last_accessed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class TranslationReviewHistory(Base, TimestampMixin):
    """
    Dedicated audit history for translation lifecycle and human editorial review.
    Captures state transitions (Pending -> Generated -> Needs Review -> Approved / Rejected).
    """

    __tablename__ = "translation_review_history"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    content_asset_id: Mapped[int] = mapped_column(
        ForeignKey("content_assets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    from_status: Mapped[str] = mapped_column(String(30), nullable=False)
    to_status: Mapped[str] = mapped_column(String(30), nullable=False)
    reviewer_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    review_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    content_asset: Mapped[ContentAsset] = relationship(
        "ContentAsset",
        back_populates="translation_review_history",
    )
    reviewer: Mapped[User] = relationship(
        "User",
        foreign_keys=[reviewer_id],
    )

