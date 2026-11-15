"""add_worker_lease_and_retry_backoff

Revision ID: c069b45597ab
Revises: d5ec7a12fb34
Create Date: 2026-11-03 10:05:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c069b45597ab'
down_revision: Union[str, Sequence[str], None] = 'd5ec7a12fb34'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add worker lease and stale recovery columns to distribution_jobs, and next_retry_at to delivery_records."""
    # 1. distribution_jobs lease & recovery columns
    op.add_column('distribution_jobs', sa.Column('locked_by', sa.String(length=100), nullable=True))
    op.add_column('distribution_jobs', sa.Column('locked_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('distribution_jobs', sa.Column('lease_expires_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('distribution_jobs', sa.Column('last_heartbeat_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('distribution_jobs', sa.Column('recovery_count', sa.Integer(), server_default='0', nullable=False))
    op.create_index(op.f('ix_distribution_jobs_lease_expires_at'), 'distribution_jobs', ['lease_expires_at'], unique=False)

    # 2. delivery_records next_retry_at column
    op.add_column('delivery_records', sa.Column('next_retry_at', sa.DateTime(timezone=True), nullable=True))
    op.create_index(op.f('ix_delivery_records_next_retry_at'), 'delivery_records', ['next_retry_at'], unique=False)


def downgrade() -> None:
    """Remove worker lease columns and next_retry_at column."""
    op.drop_index(op.f('ix_delivery_records_next_retry_at'), table_name='delivery_records')
    op.drop_column('delivery_records', 'next_retry_at')

    op.drop_index(op.f('ix_distribution_jobs_lease_expires_at'), table_name='distribution_jobs')
    op.drop_column('distribution_jobs', 'recovery_count')
    op.drop_column('distribution_jobs', 'last_heartbeat_at')
    op.drop_column('distribution_jobs', 'lease_expires_at')
    op.drop_column('distribution_jobs', 'locked_at')
    op.drop_column('distribution_jobs', 'locked_by')

