from __future__ import annotations
from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import String, Integer, Boolean, Index, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.communication import Message, Feedback


class AudienceMember(Base, TimestampMixin):
    """Audience member entity representing public citizens, students, employees, or recipients."""

    __tablename__ = "audience_members"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    phone: Mapped[Optional[str]] = mapped_column(String(30), nullable=True, index=True)
    age: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    gender: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    state: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    preferred_language: Mapped[str] = mapped_column(
        String(50), nullable=False, default="en", index=True
    )
    occupation: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    organization_department: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    preferred_channel: Mapped[str] = mapped_column(
        String(30), nullable=False, default="Email", index=True
    )
    consent_status: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    messages: Mapped[List[Message]] = relationship(back_populates="audience_member")
    feedbacks: Mapped[List[Feedback]] = relationship(back_populates="audience_member")

    __table_args__ = (
        Index(
            "uq_audience_members_email",
            "email",
            unique=True,
            postgresql_where=text("email IS NOT NULL"),
        ),
        Index(
            "uq_audience_members_phone",
            "phone",
            unique=True,
            postgresql_where=text("phone IS NOT NULL"),
        ),
    )
