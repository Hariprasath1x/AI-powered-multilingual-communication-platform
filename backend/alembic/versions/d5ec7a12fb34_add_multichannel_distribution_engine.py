"""add_multichannel_distribution_engine

Revision ID: d5ec7a12fb34
Revises: c4fb6902ef23
Create Date: 2026-11-03 10:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'd5ec7a12fb34'
down_revision: Union[str, Sequence[str], None] = 'c4fb6902ef23'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create distribution_jobs, delivery_records, and delivery_attempts tables."""
    # 1. distribution_jobs
    op.create_table(
        'distribution_jobs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('job_id', sa.String(length=36), nullable=False),
        sa.Column('campaign_id', sa.Integer(), nullable=False),
        sa.Column('content_asset_id', sa.Integer(), nullable=True),
        sa.Column('template_id', sa.Integer(), nullable=True),
        sa.Column('channel', sa.String(length=30), nullable=False),
        sa.Column('status', sa.String(length=30), server_default='pending', nullable=False),
        sa.Column('total_recipients', sa.Integer(), server_default='0', nullable=False),
        sa.Column('eligible_recipients', sa.Integer(), server_default='0', nullable=False),
        sa.Column('queued_recipients', sa.Integer(), server_default='0', nullable=False),
        sa.Column('sent_recipients', sa.Integer(), server_default='0', nullable=False),
        sa.Column('delivered_recipients', sa.Integer(), server_default='0', nullable=False),
        sa.Column('failed_recipients', sa.Integer(), server_default='0', nullable=False),
        sa.Column('skipped_recipients', sa.Integer(), server_default='0', nullable=False),
        sa.Column('error_summary', sa.Text(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['campaign_id'], ['campaigns.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['content_asset_id'], ['content_assets.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['template_id'], ['templates.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_distribution_jobs_id'), 'distribution_jobs', ['id'], unique=False)
    op.create_index(op.f('ix_distribution_jobs_job_id'), 'distribution_jobs', ['job_id'], unique=True)
    op.create_index(op.f('ix_distribution_jobs_campaign_id'), 'distribution_jobs', ['campaign_id'], unique=False)
    op.create_index(op.f('ix_distribution_jobs_content_asset_id'), 'distribution_jobs', ['content_asset_id'], unique=False)
    op.create_index(op.f('ix_distribution_jobs_template_id'), 'distribution_jobs', ['template_id'], unique=False)
    op.create_index(op.f('ix_distribution_jobs_channel'), 'distribution_jobs', ['channel'], unique=False)
    op.create_index(op.f('ix_distribution_jobs_status'), 'distribution_jobs', ['status'], unique=False)
    op.create_index(op.f('ix_distribution_jobs_created_by'), 'distribution_jobs', ['created_by'], unique=False)

    # 2. delivery_records
    op.create_table(
        'delivery_records',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('delivery_id', sa.String(length=36), nullable=False),
        sa.Column('job_id', sa.Integer(), nullable=False),
        sa.Column('audience_member_id', sa.Integer(), nullable=False),
        sa.Column('channel', sa.String(length=30), nullable=False),
        sa.Column('recipient_address', sa.String(length=255), nullable=False),
        sa.Column('rendered_content', sa.Text(), nullable=False),
        sa.Column('delivery_status', sa.String(length=30), server_default='pending', nullable=False),
        sa.Column('provider_name', sa.String(length=50), nullable=True),
        sa.Column('provider_reference', sa.String(length=100), nullable=True),
        sa.Column('attempt_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('max_attempts', sa.Integer(), server_default='3', nullable=False),
        sa.Column('last_attempt_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('delivered_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('error_code', sa.String(length=50), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('idempotency_key', sa.String(length=128), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['job_id'], ['distribution_jobs.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['audience_member_id'], ['audience_members.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('job_id', 'audience_member_id', 'channel', name='uq_job_recipient_channel'),
    )
    op.create_index(op.f('ix_delivery_records_id'), 'delivery_records', ['id'], unique=False)
    op.create_index(op.f('ix_delivery_records_delivery_id'), 'delivery_records', ['delivery_id'], unique=True)
    op.create_index(op.f('ix_delivery_records_job_id'), 'delivery_records', ['job_id'], unique=False)
    op.create_index(op.f('ix_delivery_records_audience_member_id'), 'delivery_records', ['audience_member_id'], unique=False)
    op.create_index(op.f('ix_delivery_records_channel'), 'delivery_records', ['channel'], unique=False)
    op.create_index(op.f('ix_delivery_records_delivery_status'), 'delivery_records', ['delivery_status'], unique=False)
    op.create_index(op.f('ix_delivery_records_provider_reference'), 'delivery_records', ['provider_reference'], unique=False)
    op.create_index(op.f('ix_delivery_records_error_code'), 'delivery_records', ['error_code'], unique=False)
    op.create_index(op.f('ix_delivery_records_idempotency_key'), 'delivery_records', ['idempotency_key'], unique=True)

    # 3. delivery_attempts
    op.create_table(
        'delivery_attempts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('delivery_record_id', sa.Integer(), nullable=False),
        sa.Column('attempt_number', sa.Integer(), nullable=False),
        sa.Column('provider_name', sa.String(length=50), nullable=False),
        sa.Column('attempt_status', sa.String(length=30), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('error_code', sa.String(length=50), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('response_metadata', postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), 'sqlite'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['delivery_record_id'], ['delivery_records.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_delivery_attempts_id'), 'delivery_attempts', ['id'], unique=False)
    op.create_index(op.f('ix_delivery_attempts_delivery_record_id'), 'delivery_attempts', ['delivery_record_id'], unique=False)


def downgrade() -> None:
    """Drop delivery_attempts, delivery_records, and distribution_jobs tables."""
    op.drop_table('delivery_attempts')
    op.drop_table('delivery_records')
    op.drop_table('distribution_jobs')

