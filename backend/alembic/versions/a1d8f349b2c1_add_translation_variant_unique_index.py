"""add_translation_variant_unique_index

Revision ID: a1d8f349b2c1
Revises: f4b8c12a7d3e
Create Date: 2026-11-09 23:05:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1d8f349b2c1'
down_revision: Union[str, Sequence[str], None] = 'f4b8c12a7d3e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create partial unique index on content_assets(parent_id, lower(target_language))."""
    op.create_index(
        'uq_content_asset_translation_variant',
        'content_assets',
        ['parent_id', sa.text('lower(target_language)')],
        unique=True,
        postgresql_where=sa.text('parent_id IS NOT NULL AND target_language IS NOT NULL'),
        sqlite_where=sa.text('parent_id IS NOT NULL AND target_language IS NOT NULL'),
    )


def downgrade() -> None:
    """Drop partial unique index on content_assets."""
    op.drop_index(
        'uq_content_asset_translation_variant',
        table_name='content_assets',
    )

