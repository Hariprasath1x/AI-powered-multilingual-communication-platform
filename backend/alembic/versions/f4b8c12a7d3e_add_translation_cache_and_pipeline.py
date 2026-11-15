"""add_translation_cache_and_pipeline

Revision ID: f4b8c12a7d3e
Revises: c069b45597ab
Create Date: 2026-11-06 23:45:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'f4b8c12a7d3e'
down_revision: Union[str, Sequence[str], None] = 'c069b45597ab'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create translation_cache and translation_review_history tables with indexes and constraints."""
    # 1. Translation Cache Table
    op.create_table(
        'translation_cache',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('cache_key', sa.String(length=64), nullable=False),
        sa.Column('source_content_hash', sa.String(length=64), nullable=False),
        sa.Column('source_language', sa.String(length=10), nullable=False),
        sa.Column('target_language', sa.String(length=10), nullable=False),
        sa.Column('channel', sa.String(length=30), nullable=False, server_default='Email'),
        sa.Column('translated_title', sa.String(length=255), nullable=False),
        sa.Column('translated_body', sa.Text(), nullable=False),
        sa.Column('translated_call_to_action', sa.String(length=255), nullable=True),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column(
            'preserved_placeholders',
            postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), 'sqlite'),
            nullable=False,
            server_default='[]',
        ),
        sa.Column(
            'provider_metadata',
            postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), 'sqlite'),
            nullable=True,
        ),
        sa.Column('hit_count', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('last_accessed_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_translation_cache_id'), 'translation_cache', ['id'], unique=False)
    op.create_index(op.f('ix_translation_cache_cache_key'), 'translation_cache', ['cache_key'], unique=True)
    op.create_index(op.f('ix_translation_cache_source_content_hash'), 'translation_cache', ['source_content_hash'], unique=False)
    op.create_index(op.f('ix_translation_cache_source_language'), 'translation_cache', ['source_language'], unique=False)
    op.create_index(op.f('ix_translation_cache_target_language'), 'translation_cache', ['target_language'], unique=False)

    # 2. Translation Review History Table
    op.create_table(
        'translation_review_history',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('content_asset_id', sa.Integer(), nullable=False),
        sa.Column('from_status', sa.String(length=30), nullable=False),
        sa.Column('to_status', sa.String(length=30), nullable=False),
        sa.Column('reviewer_id', sa.Integer(), nullable=False),
        sa.Column('review_notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['content_asset_id'], ['content_assets.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['reviewer_id'], ['users.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_translation_review_history_id'), 'translation_review_history', ['id'], unique=False)
    op.create_index(op.f('ix_translation_review_history_content_asset_id'), 'translation_review_history', ['content_asset_id'], unique=False)
    op.create_index(op.f('ix_translation_review_history_reviewer_id'), 'translation_review_history', ['reviewer_id'], unique=False)


def downgrade() -> None:
    """Drop translation_review_history and translation_cache tables and indexes."""
    op.drop_index(op.f('ix_translation_review_history_reviewer_id'), table_name='translation_review_history')
    op.drop_index(op.f('ix_translation_review_history_content_asset_id'), table_name='translation_review_history')
    op.drop_index(op.f('ix_translation_review_history_id'), table_name='translation_review_history')
    op.drop_table('translation_review_history')

    op.drop_index(op.f('ix_translation_cache_target_language'), table_name='translation_cache')
    op.drop_index(op.f('ix_translation_cache_source_language'), table_name='translation_cache')
    op.drop_index(op.f('ix_translation_cache_source_content_hash'), table_name='translation_cache')
    op.drop_index(op.f('ix_translation_cache_cache_key'), table_name='translation_cache')
    op.drop_index(op.f('ix_translation_cache_id'), table_name='translation_cache')
    op.drop_table('translation_cache')

