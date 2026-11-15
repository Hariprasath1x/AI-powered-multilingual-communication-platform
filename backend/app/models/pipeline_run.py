"""SQLAlchemy model for end-to-end content generation pipeline runs (Milestone 2, Task 12)."""

from __future__ import annotations
from typing import TYPE_CHECKING, Optional, Dict, Any, List
from datetime import datetime
from sqlalchemy import String, Text, ForeignKey, DateTime, Integer
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.campaign import Campaign


class ContentPipelineRun(Base, TimestampMixin):
    """
    Persistent record of an end-to-end automated content generation pipeline execution.
    Orchestrates: Generate -> Translate -> Personalize -> Tone Optimize -> Review.
    Tracks intermediate stage outputs, generated asset IDs, and resumption state.
    """

    __tablename__ = "content_pipeline_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    campaign_id: Mapped[int] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="pending",
        index=True,
        comment="pending, in_progress, completed, partially_completed, failed, cancelled",
    )

    current_stage: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="generate",
        index=True,
        comment="generate, translate, personalize, tone_optimize, review, completed",
    )

    total_stages: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=5,
    )

    completed_stages: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    idempotency_key: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        index=True,
    )

    config: Mapped[Dict[str, Any]] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"),
        nullable=False,
        default=dict,
        comment="Input parameters: topic, objective, channels, languages, segments, tone",
    )

    stage_outputs: Mapped[Dict[str, Any]] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"),
        nullable=False,
        default=dict,
        comment="Execution results for each completed stage",
    )

    generated_asset_ids: Mapped[List[int]] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"),
        nullable=False,
        default=list,
        comment="List of ContentAsset IDs created/managed by this pipeline run",
    )

    generated_variant_ids: Mapped[List[int]] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"),
        nullable=False,
        default=list,
        comment="List of ContentVariant IDs created/managed by this pipeline run",
    )

    error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    created_by: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    campaign: Mapped[Campaign] = relationship(
        "Campaign",
        back_populates="pipeline_runs",
    )
    creator: Mapped[User] = relationship(
        "User",
        foreign_keys=[created_by],
    )

