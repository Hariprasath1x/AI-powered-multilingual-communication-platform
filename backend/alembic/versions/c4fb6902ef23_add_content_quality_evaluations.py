"""add_content_quality_evaluations

Revision ID: c4fb6902ef23
Revises: b3ea5891de12
Create Date: 2026-10-30 15:45:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'c4fb6902ef23'
down_revision: Union[str, Sequence[str], None] = 'b3ea5891de12'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create content_quality_assessments and content_quality_findings tables."""
    # 1. content_quality_assessments
    op.create_table(
        'content_quality_assessments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('content_asset_id', sa.Integer(), nullable=False),
        sa.Column('content_version_hash', sa.String(length=64), nullable=False),
        sa.Column('overall_score', sa.Float(), nullable=False),
        sa.Column('status', sa.String(length=30), server_default='completed', nullable=False),
        sa.Column('dimension_scores', postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), 'sqlite'), nullable=False),
        sa.Column('evaluator_type', sa.String(length=30), server_default='hybrid', nullable=False),
        sa.Column('evaluator_metadata', postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), 'sqlite'), nullable=True),
        sa.Column('critical_issues_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('high_issues_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('medium_issues_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('low_issues_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('info_issues_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('created_by', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['content_asset_id'], ['content_assets.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_content_quality_assessments_id'), 'content_quality_assessments', ['id'], unique=False)
    op.create_index(op.f('ix_content_quality_assessments_content_asset_id'), 'content_quality_assessments', ['content_asset_id'], unique=False)
    op.create_index(op.f('ix_content_quality_assessments_content_version_hash'), 'content_quality_assessments', ['content_version_hash'], unique=False)
    op.create_index(op.f('ix_content_quality_assessments_status'), 'content_quality_assessments', ['status'], unique=False)
    op.create_index(op.f('ix_content_quality_assessments_created_by'), 'content_quality_assessments', ['created_by'], unique=False)

    # 2. content_quality_findings
    op.create_table(
        'content_quality_findings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('assessment_id', sa.Integer(), nullable=False),
        sa.Column('category', sa.String(length=50), nullable=False),
        sa.Column('severity', sa.String(length=20), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('explanation', sa.Text(), nullable=False),
        sa.Column('affected_text', sa.Text(), nullable=True),
        sa.Column('suggested_correction', sa.Text(), nullable=True),
        sa.Column('evaluation_source', sa.String(length=30), server_default='deterministic', nullable=False),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('rule_id', sa.String(length=50), nullable=True),
        sa.Column('reviewer_decision', sa.String(length=30), server_default='pending', nullable=False),
        sa.Column('decision_notes', sa.Text(), nullable=True),
        sa.Column('resolved_by', sa.Integer(), nullable=True),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['assessment_id'], ['content_quality_assessments.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['resolved_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_content_quality_findings_id'), 'content_quality_findings', ['id'], unique=False)
    op.create_index(op.f('ix_content_quality_findings_assessment_id'), 'content_quality_findings', ['assessment_id'], unique=False)
    op.create_index(op.f('ix_content_quality_findings_category'), 'content_quality_findings', ['category'], unique=False)
    op.create_index(op.f('ix_content_quality_findings_severity'), 'content_quality_findings', ['severity'], unique=False)
    op.create_index(op.f('ix_content_quality_findings_reviewer_decision'), 'content_quality_findings', ['reviewer_decision'], unique=False)


def downgrade() -> None:
    """Drop content_quality_findings and content_quality_assessments tables."""
    op.drop_index(op.f('ix_content_quality_findings_reviewer_decision'), table_name='content_quality_findings')
    op.drop_index(op.f('ix_content_quality_findings_severity'), table_name='content_quality_findings')
    op.drop_index(op.f('ix_content_quality_findings_category'), table_name='content_quality_findings')
    op.drop_index(op.f('ix_content_quality_findings_assessment_id'), table_name='content_quality_findings')
    op.drop_index(op.f('ix_content_quality_findings_id'), table_name='content_quality_findings')
    op.drop_table('content_quality_findings')

    op.drop_index(op.f('ix_content_quality_assessments_created_by'), table_name='content_quality_assessments')
    op.drop_index(op.f('ix_content_quality_assessments_status'), table_name='content_quality_assessments')
    op.drop_index(op.f('ix_content_quality_assessments_content_version_hash'), table_name='content_quality_assessments')
    op.drop_index(op.f('ix_content_quality_assessments_content_asset_id'), table_name='content_quality_assessments')
    op.drop_index(op.f('ix_content_quality_assessments_id'), table_name='content_quality_assessments')
    op.drop_table('content_quality_assessments')

