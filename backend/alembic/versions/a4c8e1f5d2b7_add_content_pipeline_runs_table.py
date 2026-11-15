"""add_content_pipeline_runs_table

Revision ID: a4c8e1f5d2b7
Revises: b7d4e1f8a29c
Create Date: 2026-11-15 23:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'a4c8e1f5d2b7'
down_revision: Union[str, Sequence[str], None] = 'b7d4e1f8a29c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create content_pipeline_runs table and indexes."""
    op.create_table(
        'content_pipeline_runs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('campaign_id', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=30), server_default='pending', nullable=False),
        sa.Column('current_stage', sa.String(length=30), server_default='generate', nullable=False),
        sa.Column('total_stages', sa.Integer(), server_default='5', nullable=False),
        sa.Column('completed_stages', sa.Integer(), server_default='0', nullable=False),
        sa.Column('idempotency_key', sa.String(length=100), nullable=True),
        sa.Column('config', postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), 'sqlite'), nullable=False),
        sa.Column('stage_outputs', postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), 'sqlite'), nullable=False),
        sa.Column('generated_asset_ids', postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), 'sqlite'), nullable=False),
        sa.Column('generated_variant_ids', postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), 'sqlite'), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['campaign_id'], ['campaigns.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_index(op.f('ix_content_pipeline_runs_id'), 'content_pipeline_runs', ['id'], unique=False)
    op.create_index(op.f('ix_content_pipeline_runs_campaign_id'), 'content_pipeline_runs', ['campaign_id'], unique=False)
    op.create_index(op.f('ix_content_pipeline_runs_status'), 'content_pipeline_runs', ['status'], unique=False)
    op.create_index(op.f('ix_content_pipeline_runs_current_stage'), 'content_pipeline_runs', ['current_stage'], unique=False)
    op.create_index(op.f('ix_content_pipeline_runs_idempotency_key'), 'content_pipeline_runs', ['idempotency_key'], unique=False)
    op.create_index(op.f('ix_content_pipeline_runs_created_by'), 'content_pipeline_runs', ['created_by'], unique=False)


def downgrade() -> None:
    """Drop content_pipeline_runs table and indexes."""
    op.drop_index(op.f('ix_content_pipeline_runs_created_by'), table_name='content_pipeline_runs')
    op.drop_index(op.f('ix_content_pipeline_runs_idempotency_key'), table_name='content_pipeline_runs')
    op.drop_index(op.f('ix_content_pipeline_runs_current_stage'), table_name='content_pipeline_runs')
    op.drop_index(op.f('ix_content_pipeline_runs_status'), table_name='content_pipeline_runs')
    op.drop_index(op.f('ix_content_pipeline_runs_campaign_id'), table_name='content_pipeline_runs')
    op.drop_index(op.f('ix_content_pipeline_runs_id'), table_name='content_pipeline_runs')
    op.drop_table('content_pipeline_runs')

