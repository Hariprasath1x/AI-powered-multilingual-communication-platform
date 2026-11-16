"""Add channel_configurations table and extend messages table for Task 13.

Revision ID: c5e8b2d1f4a9
Revises: a4c8e1f5d2b7
Create Date: 2026-11-16 12:35:00.000000
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "c5e8b2d1f4a9"
down_revision: Union[str, None] = "a4c8e1f5d2b7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create channel_configurations table
    op.create_table(
        "channel_configurations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("channel", sa.String(length=30), nullable=False, comment="Email, SMS, WhatsApp, Voice, Web"),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("provider_type", sa.String(length=50), nullable=False, server_default="mock"),
        sa.Column("sender_address", sa.String(length=255), nullable=True),
        sa.Column("sender_name", sa.String(length=255), nullable=True),
        sa.Column(
            "credentials",
            postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), "sqlite"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_channel_configurations_id", "channel_configurations", ["id"], unique=False)
    op.create_index("ix_channel_configurations_channel", "channel_configurations", ["channel"], unique=True)

    # Pre-populate default Email and SMS mock channel configurations
    op.execute(
        """
        INSERT INTO channel_configurations (channel, is_enabled, provider_type, sender_address, sender_name, credentials, created_at, updated_at)
        VALUES 
            ('Email', true, 'mock', 'notifications@masscomm.gov.in', 'MassCommAI Citizen Communications', '{}'::jsonb, NOW(), NOW()),
            ('SMS', true, 'mock', 'GOVMSG', 'Govt Citizen Alert', '{}'::jsonb, NOW(), NOW())
        ON CONFLICT (channel) DO NOTHING;
        """
    )

    # 2. Extend messages table with tracking, content references, provider ID, failure reason, delivered_at, and updated_at
    op.add_column("messages", sa.Column("tracking_id", sa.String(length=64), nullable=True))
    op.add_column("messages", sa.Column("content_asset_id", sa.Integer(), nullable=True))
    op.add_column("messages", sa.Column("content_variant_id", sa.Integer(), nullable=True))
    op.add_column("messages", sa.Column("provider_message_id", sa.String(length=100), nullable=True))
    op.add_column("messages", sa.Column("failure_reason", sa.Text(), nullable=True))
    op.add_column("messages", sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("messages", sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False))

    # Backfill tracking_id for any pre-existing messages
    op.execute("UPDATE messages SET tracking_id = 'trk_' || substr(md5(random()::text || id::text), 1, 24) WHERE tracking_id IS NULL")

    # Alter tracking_id to NOT NULL and add unique index
    op.alter_column("messages", "tracking_id", nullable=False)
    op.create_index("ix_messages_tracking_id", "messages", ["tracking_id"], unique=True)
    op.create_index("ix_messages_content_asset_id", "messages", ["content_asset_id"], unique=False)
    op.create_index("ix_messages_content_variant_id", "messages", ["content_variant_id"], unique=False)
    op.create_index("ix_messages_provider_message_id", "messages", ["provider_message_id"], unique=False)

    op.create_foreign_key(
        "fk_messages_content_asset_id",
        "messages",
        "content_assets",
        ["content_asset_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_messages_content_variant_id",
        "messages",
        "content_variants",
        ["content_variant_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_messages_content_variant_id", "messages", type_="foreignkey")
    op.drop_constraint("fk_messages_content_asset_id", "messages", type_="foreignkey")
    op.drop_index("ix_messages_provider_message_id", table_name="messages")
    op.drop_index("ix_messages_content_variant_id", table_name="messages")
    op.drop_index("ix_messages_content_asset_id", table_name="messages")
    op.drop_index("ix_messages_tracking_id", table_name="messages")

    op.drop_column("messages", "updated_at")
    op.drop_column("messages", "delivered_at")
    op.drop_column("messages", "failure_reason")
    op.drop_column("messages", "provider_message_id")
    op.drop_column("messages", "content_variant_id")
    op.drop_column("messages", "content_asset_id")
    op.drop_column("messages", "tracking_id")

    op.drop_index("ix_channel_configurations_channel", table_name="channel_configurations")
    op.drop_index("ix_channel_configurations_id", table_name="channel_configurations")
    op.drop_table("channel_configurations")

