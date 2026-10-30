from __future__ import annotations
from typing import TYPE_CHECKING, List, Optional
from datetime import datetime
from sqlalchemy import String, Boolean, ForeignKey, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.segment import Segment
    from app.models.campaign import Campaign
    from app.models.template import Template
    from app.models.content_asset import ContentAsset


class Role(Base):
    """Role model defining access levels (Admin, Campaign Manager, Communication Team)."""

    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    users: Mapped[List[User]] = relationship(back_populates="role")


class User(Base, TimestampMixin):
    """User account entity with role assignment and organization context."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    phone: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    organization: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id", ondelete="RESTRICT"), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    role: Mapped[Role] = relationship(back_populates="users")
    created_segments: Mapped[List[Segment]] = relationship(back_populates="creator")
    created_campaigns: Mapped[List[Campaign]] = relationship(back_populates="creator")
    created_templates: Mapped[List[Template]] = relationship(back_populates="creator")
    created_content_assets: Mapped[List[ContentAsset]] = relationship(
        "ContentAsset",
        foreign_keys="ContentAsset.created_by",
        back_populates="creator",
    )

