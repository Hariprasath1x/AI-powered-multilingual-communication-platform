from __future__ import annotations
from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import String, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.communication import Message


class Template(Base, TimestampMixin):
    """Reusable communication template supporting dynamic placeholders like {name} and {area}."""

    __tablename__ = "templates"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    category: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Healthcare, Disaster, Education, Governance, etc.",
    )
    body: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Template content body with placeholders like {name}, {area}",
    )
    language: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="en",
        index=True,
    )
    tags: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Comma-separated keyword tags",
    )
    created_by: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    # Relationships
    creator: Mapped[User] = relationship(back_populates="created_templates")
    messages: Mapped[List[Message]] = relationship(back_populates="template")

