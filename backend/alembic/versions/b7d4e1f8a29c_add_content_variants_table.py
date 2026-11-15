"""add_content_variants_table

Revision ID: b7d4e1f8a29c
Revises: e6c7d81a9f02
Create Date: 2026-11-15 17:55:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b7d4e1f8a29c'
down_revision: Union[str, Sequence[str], None] = 'e6c7d81a9f02'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create content_variants table and corresponding indexes."""
    op.create_table(
        'content_variants',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('campaign_id', sa.Integer(), nullable=False),
        sa.Column('source_content_id', sa.Integer(), nullable=False),
        sa.Column('segment_id', sa.Integer(), nullable=True),
        sa.Column('language', sa.String(length=10), server_default='en', nullable=False),
        sa.Column('channel', sa.String(length=30), server_default='Email', nullable=False),
        sa.Column('variant_title', sa.String(length=255), nullable=False),
        sa.Column('variant_body', sa.Text(), nullable=False),
        sa.Column('variant_cta', sa.String(length=255), nullable=True),
        sa.Column('personalization_notes', sa.Text(), nullable=True),
        sa.Column('review_status', sa.String(length=30), server_default='Draft', nullable=False),
        sa.Column('review_notes', sa.Text(), nullable=True),
        sa.Column('reviewed_by', sa.Integer(), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('assessment_id', sa.Integer(), nullable=True),
        sa.Column('content_version_hash', sa.String(length=64), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['campaign_id'], ['campaigns.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['source_content_id'], ['content_assets.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['segment_id'], ['segments.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['reviewed_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['assessment_id'], ['content_quality_assessments.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_index(op.f('ix_content_variants_id'), 'content_variants', ['id'], unique=False)
    op.create_index(op.f('ix_content_variants_campaign_id'), 'content_variants', ['campaign_id'], unique=False)
    op.create_index(op.f('ix_content_variants_source_content_id'), 'content_variants', ['source_content_id'], unique=False)
    op.create_index(op.f('ix_content_variants_segment_id'), 'content_variants', ['segment_id'], unique=False)
    op.create_index(op.f('ix_content_variants_language'), 'content_variants', ['language'], unique=False)
    op.create_index(op.f('ix_content_variants_channel'), 'content_variants', ['channel'], unique=False)
    op.create_index(op.f('ix_content_variants_review_status'), 'content_variants', ['review_status'], unique=False)
    op.create_index(op.f('ix_content_variants_created_by'), 'content_variants', ['created_by'], unique=False)

    # Unique functional index enforcing uniqueness for (source_content_id, segment_id, lower(language))
    op.create_index(
        'uq_content_variant_source_segment_lang',
        'content_variants',
        ['source_content_id', 'segment_id', sa.text('lower(language)')],
        unique=True,
        postgresql_where=sa.text('segment_id IS NOT NULL'),
    )

    # Unique functional index enforcing uniqueness when segment_id IS NULL
    op.create_index(
        'uq_content_variant_source_lang_no_segment',
        'content_variants',
        ['source_content_id', sa.text('lower(language)')],
        unique=True,
        postgresql_where=sa.text('segment_id IS NULL'),
    )


def downgrade() -> None:
    """Drop content_variants table and corresponding indexes."""
    op.drop_index('uq_content_variant_source_lang_no_segment', table_name='content_variants')
    op.drop_index('uq_content_variant_source_segment_lang', table_name='content_variants')
    op.drop_index(op.f('ix_content_variants_created_by'), table_name='content_variants')
    op.drop_index(op.f('ix_content_variants_review_status'), table_name='content_variants')
    op.drop_index(op.f('ix_content_variants_channel'), table_name='content_variants')
    op.drop_index(op.f('ix_content_variants_language'), table_name='content_variants')
    op.drop_index(op.f('ix_content_variants_segment_id'), table_name='content_variants')
    op.drop_index(op.f('ix_content_variants_source_content_id'), table_name='content_variants')
    op.drop_index(op.f('ix_content_variants_campaign_id'), table_name='content_variants')
    op.drop_index(op.f('ix_content_variants_id'), table_name='content_variants')
    op.drop_table('content_variants')

