"""allow_nullable_consent_status

Revision ID: 1a2b3c4d5e6f
Revises: 0de49a2cf7ef
Create Date: 2026-10-29 14:10:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '1a2b3c4d5e6f'
down_revision: Union[str, Sequence[str], None] = '0de49a2cf7ef'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Make consent_status nullable to represent unknown/unconfirmed consent distinctly from opt-in and opt-out."""
    op.alter_column(
        'audience_members',
        'consent_status',
        existing_type=sa.Boolean(),
        nullable=True,
        server_default=None,
    )


def downgrade() -> None:
    """Revert consent_status to non-nullable boolean, defaulting nulls to False (unconsented)."""
    op.execute("UPDATE audience_members SET consent_status = False WHERE consent_status IS NULL")
    op.alter_column(
        'audience_members',
        'consent_status',
        existing_type=sa.Boolean(),
        nullable=False,
        server_default=sa.text('false'),
    )

