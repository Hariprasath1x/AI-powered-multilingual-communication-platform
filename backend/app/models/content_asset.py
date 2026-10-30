"""ContentAsset ORM model for storing generated, translated, and edited public awareness copy."""

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
    from app.models.campaign import Campaign
    from app.models.template import Template


class ContentAsset(Base, TimestampMixin):
    """
    Persistent content asset representing public awareness copy.
    Maintains full version traceability, translation variant chaining,
    human review lifecycle, and campaign/template association.
    """

    __tablename__ = "content_assets"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    call_to_action: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    category: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Healthcare, Disaster Preparedness, Education, Civic Services, Environment, etc.",
    )
    tone: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="informative",
        comment="formal, informative, friendly, urgent, empathetic",
    )
    channel: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        index=True,
        comment="Email, SMS, WhatsApp, Voice",
    )
    source_language: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="en",
        index=True,
    )
    target_language: Mapped[Optional[str]] = mapped_column(
        String(10),
        nullable=True,
        index=True,
    )
    operation_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="generation",
        index=True,
        comment="generation, translation, human_edit",
    )

    # Chaining & Version Lineage: Points to original/source asset if this is a translation or edit
    parent_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("content_assets.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Optional linkages to campaigns and templates
    campaign_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("campaigns.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    template_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("templates.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Human Review & Lifecycle
    review_status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="Draft",
        index=True,
        comment="Draft, In Review, Approved, Rejected",
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

    # Safe Provider Metadata (model name, tokens used, provider name - strictly NO secrets)
    provider_metadata: Mapped[Optional[Any]] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"),
        nullable=True,
        default=dict,
    )

    # Authorship
    created_by: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    # Relationships
    creator: Mapped[User] = relationship(
        "User",
        foreign_keys=[created_by],
        back_populates="created_content_assets",
    )
    reviewer: Mapped[Optional[User]] = relationship(
        "User",
        foreign_keys=[reviewed_by],
    )
    campaign: Mapped[Optional[Campaign]] = relationship(
        "Campaign",
        back_populates="content_assets",
    )
    template: Mapped[Optional[Template]] = relationship(
        "Template",
        back_populates="content_assets",
    )
    parent: Mapped[Optional[ContentAsset]] = relationship(
        "ContentAsset",
        remote_side=[id],
        back_populates="variants",
    )
    variants: Mapped[List[ContentAsset]] = relationship(
        "ContentAsset",
        back_populates="parent",
    )

