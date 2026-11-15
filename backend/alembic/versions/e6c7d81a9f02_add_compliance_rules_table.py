"""add_compliance_rules_table

Revision ID: e6c7d81a9f02
Revises: a1d8f349b2c1
Create Date: 2026-11-12 22:45:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e6c7d81a9f02'
down_revision: Union[str, Sequence[str], None] = 'a1d8f349b2c1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create compliance_rules table and corresponding indexes."""
    op.create_table(
        'compliance_rules',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('rule_code', sa.String(length=50), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('rule_type', sa.String(length=30), nullable=False),
        sa.Column('pattern', sa.Text(), nullable=False),
        sa.Column('severity', sa.String(length=20), server_default='critical', nullable=False),
        sa.Column('organization', sa.String(length=150), nullable=True),
        sa.Column('is_global', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('channel', sa.String(length=30), nullable=True),
        sa.Column('language', sa.String(length=10), nullable=True),
        sa.Column('suggested_action', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('created_by', sa.Integer(), nullable=False),
        sa.Column('updated_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['updated_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_index(op.f('ix_compliance_rules_id'), 'compliance_rules', ['id'], unique=False)
    op.create_index(op.f('ix_compliance_rules_rule_code'), 'compliance_rules', ['rule_code'], unique=True)
    op.create_index(op.f('ix_compliance_rules_name'), 'compliance_rules', ['name'], unique=False)
    op.create_index(op.f('ix_compliance_rules_rule_type'), 'compliance_rules', ['rule_type'], unique=False)
    op.create_index(op.f('ix_compliance_rules_severity'), 'compliance_rules', ['severity'], unique=False)
    op.create_index(op.f('ix_compliance_rules_organization'), 'compliance_rules', ['organization'], unique=False)
    op.create_index(op.f('ix_compliance_rules_is_global'), 'compliance_rules', ['is_global'], unique=False)
    op.create_index(op.f('ix_compliance_rules_channel'), 'compliance_rules', ['channel'], unique=False)
    op.create_index(op.f('ix_compliance_rules_language'), 'compliance_rules', ['language'], unique=False)
    op.create_index(op.f('ix_compliance_rules_is_active'), 'compliance_rules', ['is_active'], unique=False)
    op.create_index(op.f('ix_compliance_rules_created_by'), 'compliance_rules', ['created_by'], unique=False)
    op.create_index('ix_compliance_rules_org_active', 'compliance_rules', ['organization', 'is_active'], unique=False)
    op.create_index('ix_compliance_rules_lookup', 'compliance_rules', ['is_active', 'is_global', 'rule_type'], unique=False)


def downgrade() -> None:
    """Drop compliance_rules table and indexes."""
    op.drop_index('ix_compliance_rules_lookup', table_name='compliance_rules')
    op.drop_index('ix_compliance_rules_org_active', table_name='compliance_rules')
    op.drop_index(op.f('ix_compliance_rules_created_by'), table_name='compliance_rules')
    op.drop_index(op.f('ix_compliance_rules_is_active'), table_name='compliance_rules')
    op.drop_index(op.f('ix_compliance_rules_language'), table_name='compliance_rules')
    op.drop_index(op.f('ix_compliance_rules_channel'), table_name='compliance_rules')
    op.drop_index(op.f('ix_compliance_rules_is_global'), table_name='compliance_rules')
    op.drop_index(op.f('ix_compliance_rules_organization'), table_name='compliance_rules')
    op.drop_index(op.f('ix_compliance_rules_severity'), table_name='compliance_rules')
    op.drop_index(op.f('ix_compliance_rules_rule_type'), table_name='compliance_rules')
    op.drop_index(op.f('ix_compliance_rules_name'), table_name='compliance_rules')
    op.drop_index(op.f('ix_compliance_rules_rule_code'), table_name='compliance_rules')
    op.drop_index(op.f('ix_compliance_rules_id'), table_name='compliance_rules')
    op.drop_table('compliance_rules')

