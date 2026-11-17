"""Add index on messages.created_at and feedback.created_at for query performance.

Revision ID: b9c3d1e2f4a5
Revises: f8b2c5d4e3a6
Create Date: 2026-11-18 00:30:00.000000
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "b9c3d1e2f4a5"
down_revision: Union[str, None] = "f8b2c5d4e3a6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create index on messages.created_at
    try:
        op.create_index(
            op.f("ix_messages_created_at"),
            "messages",
            ["created_at"],
            unique=False,
        )
    except Exception:
        pass

    # Create index on feedback.created_at
    try:
        op.create_index(
            op.f("ix_feedback_created_at"),
            "feedback",
            ["created_at"],
            unique=False,
        )
    except Exception:
        pass


def downgrade() -> None:
    try:
        op.drop_index(op.f("ix_feedback_created_at"), table_name="feedback")
    except Exception:
        pass

    try:
        op.drop_index(op.f("ix_messages_created_at"), table_name="messages")
    except Exception:
        pass
