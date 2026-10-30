"""create_content_assets_table

Revision ID: b3ea5891de12
Revises: a2da4799cf83
Create Date: 2026-10-29 22:25:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'b3ea5891de12'
down_revision: Union[str, Sequence[str], None] = 'a2da4799cf83'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create content_assets table with foreign keys, indexes, and JSONB metadata."""
    op.create_table(
        'content_assets',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('call_to_action', sa.String(length=255), nullable=True),
        sa.Column('category', sa.String(length=50), nullable=False),
        sa.Column('tone', sa.String(length=30), nullable=False, server_default='informative'),
        sa.Column('channel', sa.String(length=30), nullable=False),
        sa.Column('source_language', sa.String(length=10), nullable=False, server_default='en'),
        sa.Column('target_language', sa.String(length=10), nullable=True),
        sa.Column('operation_type', sa.String(length=30), nullable=False, server_default='generation'),
        sa.Column('parent_id', sa.Integer(), nullable=True),
        sa.Column('campaign_id', sa.Integer(), nullable=True),
        sa.Column('template_id', sa.Integer(), nullable=True),
        sa.Column('review_status', sa.String(length=30), nullable=False, server_default='Draft'),
        sa.Column('review_notes', sa.Text(), nullable=True),
        sa.Column('reviewed_by', sa.Integer(), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('provider_metadata', postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), 'sqlite'), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['parent_id'], ['content_assets.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['campaign_id'], ['campaigns.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['template_id'], ['templates.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['reviewed_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_content_assets_id'), 'content_assets', ['id'], unique=False)
    op.create_index(op.f('ix_content_assets_title'), 'content_assets', ['title'], unique=False)
    op.create_index(op.f('ix_content_assets_category'), 'content_assets', ['category'], unique=False)
    op.create_index(op.f('ix_content_assets_channel'), 'content_assets', ['channel'], unique=False)
    op.create_index(op.f('ix_content_assets_source_language'), 'content_assets', ['source_language'], unique=False)
    op.create_index(op.f('ix_content_assets_target_language'), 'content_assets', ['target_language'], unique=False)
    op.create_index(op.f('ix_content_assets_operation_type'), 'content_assets', ['operation_type'], unique=False)
    op.create_index(op.f('ix_content_assets_parent_id'), 'content_assets', ['parent_id'], unique=False)
    op.create_index(op.f('ix_content_assets_campaign_id'), 'content_assets', ['campaign_id'], unique=False)
    op.create_index(op.f('ix_content_assets_template_id'), 'content_assets', ['template_id'], unique=False)
    op.create_index(op.f('ix_content_assets_review_status'), 'content_assets', ['review_status'], unique=False)
    op.create_index(op.f('ix_content_assets_created_by'), 'content_assets', ['created_by'], unique=False)


def downgrade() -> None:
    """Drop content_assets table and its associated indexes."""
    op.drop_index(op.f('ix_content_assets_created_by'), table_name='content_assets')
    op.drop_index(op.f('ix_content_assets_review_status'), table_name='content_assets')
    op.drop_index(op.f('ix_content_assets_template_id'), table_name='content_assets')
    op.drop_index(op.f('ix_content_assets_campaign_id'), table_name='content_assets')
    op.drop_index(op.f('ix_content_assets_parent_id'), table_name='content_assets')
    op.drop_index(op.f('ix_content_assets_operation_type'), table_name='content_assets')
    op.drop_index(op.f('ix_content_assets_target_language'), table_name='content_assets')
    op.drop_index(op.f('ix_content_assets_source_language'), table_name='content_assets')
    op.drop_index(op.f('ix_content_assets_channel'), table_name='content_assets')
    op.drop_index(op.f('ix_content_assets_category'), table_name='content_assets')
    op.drop_index(op.f('ix_content_assets_title'), table_name='content_assets')
    op.drop_index(op.f('ix_content_assets_id'), table_name='content_assets')
    op.drop_table('content_assets')

