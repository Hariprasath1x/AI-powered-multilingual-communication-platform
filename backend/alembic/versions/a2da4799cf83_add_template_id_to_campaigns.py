"""add_template_id_to_campaigns

Revision ID: a2da4799cf83
Revises: 1a2b3c4d5e6f
Create Date: 2026-10-29 15:45:09.298039

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a2da4799cf83'
down_revision: Union[str, Sequence[str], None] = '1a2b3c4d5e6f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add nullable template_id column to campaigns table with FK to templates.id and index."""
    op.add_column('campaigns', sa.Column('template_id', sa.Integer(), nullable=True))
    op.create_index(op.f('ix_campaigns_template_id'), 'campaigns', ['template_id'], unique=False)
    op.create_foreign_key(
        'fk_campaigns_template_id_templates',
        'campaigns',
        'templates',
        ['template_id'],
        ['id'],
        ondelete='SET NULL',
    )


def downgrade() -> None:
    """Remove template_id column, foreign key constraint, and index from campaigns table."""
    op.drop_constraint('fk_campaigns_template_id_templates', 'campaigns', type_='foreignkey')
    op.drop_index(op.f('ix_campaigns_template_id'), table_name='campaigns')
    op.drop_column('campaigns', 'template_id')
