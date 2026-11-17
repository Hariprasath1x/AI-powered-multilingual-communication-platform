"""Add device_tokens, web_broadcasts, webhook_events, and message fallback_attempts for Task 14.

Revision ID: d6f9c3e2b5a1
Revises: c5e8b2d1f4a9
Create Date: 2026-11-17 09:35:00.000000
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "d6f9c3e2b5a1"
down_revision: Union[str, None] = "c5e8b2d1f4a9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create device_tokens table
    op.create_table(
        "device_tokens",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("token", sa.String(length=500), nullable=False, comment="FCM registration token, Web Push subscription endpoint, or APNs hex token"),
        sa.Column("audience_member_id", sa.Integer(), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("device_type", sa.String(length=50), nullable=False, server_default="web", comment="web, android, ios"),
        sa.Column("platform_metadata", postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), "sqlite"), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["audience_member_id"], ["audience_members.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_device_tokens_id", "device_tokens", ["id"], unique=False)
    op.create_index("ix_device_tokens_token", "device_tokens", ["token"], unique=True)
    op.create_index("ix_device_tokens_audience_member_id", "device_tokens", ["audience_member_id"], unique=False)
    op.create_index("ix_device_tokens_user_id", "device_tokens", ["user_id"], unique=False)
    op.create_index("ix_device_tokens_device_type", "device_tokens", ["device_type"], unique=False)
    op.create_index("ix_device_tokens_is_active", "device_tokens", ["is_active"], unique=False)

    # 2. Create web_broadcasts table
    op.create_table(
        "web_broadcasts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("campaign_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("language", sa.String(length=30), nullable=False, server_default="en"),
        sa.Column("is_emergency", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("priority", sa.String(length=30), nullable=False, server_default="normal"),
        sa.Column("channels_dispatched", postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), "sqlite"), nullable=True),
        sa.Column("connected_clients_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("broadcast_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_web_broadcasts_id", "web_broadcasts", ["id"], unique=False)
    op.create_index("ix_web_broadcasts_campaign_id", "web_broadcasts", ["campaign_id"], unique=False)
    op.create_index("ix_web_broadcasts_language", "web_broadcasts", ["language"], unique=False)
    op.create_index("ix_web_broadcasts_is_emergency", "web_broadcasts", ["is_emergency"], unique=False)
    op.create_index("ix_web_broadcasts_broadcast_at", "web_broadcasts", ["broadcast_at"], unique=False)

    # 3. Create webhook_events table
    op.create_table(
        "webhook_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("event_id", sa.String(length=255), nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), "sqlite"), nullable=False),
        sa.Column("processed_status", sa.String(length=50), nullable=False, server_default="received"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_webhook_events_id", "webhook_events", ["id"], unique=False)
    op.create_index("ix_webhook_events_provider", "webhook_events", ["provider"], unique=False)
    op.create_index("ix_webhook_events_event_id", "webhook_events", ["event_id"], unique=True)
    op.create_index("ix_webhook_events_event_type", "webhook_events", ["event_type"], unique=False)
    op.create_index("ix_webhook_events_processed_status", "webhook_events", ["processed_status"], unique=False)

    # 4. Add fallback_attempts column to messages
    op.add_column(
        "messages",
        sa.Column(
            "fallback_attempts",
            postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), "sqlite"),
            nullable=True,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )

    # 5. Pre-populate default configurations for WhatsApp, Push, and Web
    op.execute(
        """
        INSERT INTO channel_configurations (channel, is_enabled, provider_type, sender_address, sender_name, credentials, created_at, updated_at)
        VALUES
            ('WhatsApp', true, 'mock', '+1555010099', 'MassCommAI WhatsApp Official', '{"phone_number_id": "1000000001", "waba_id": "2000000002"}'::jsonb, NOW(), NOW()),
            ('Push', true, 'mock', 'masscommai-fcm-project', 'MassCommAI Citizen Push', '{"project_id": "masscommai-mock-fcm"}'::jsonb, NOW(), NOW()),
            ('Web', true, 'mock', 'masscomm-broadcast-hub', 'MassCommAI Web Broadcast', '{}'::jsonb, NOW(), NOW())
        ON CONFLICT (channel) DO NOTHING;
        """
    )


def downgrade() -> None:
    op.drop_column("messages", "fallback_attempts")

    op.drop_index("ix_webhook_events_processed_status", table_name="webhook_events")
    op.drop_index("ix_webhook_events_event_type", table_name="webhook_events")
    op.drop_index("ix_webhook_events_event_id", table_name="webhook_events")
    op.drop_index("ix_webhook_events_provider", table_name="webhook_events")
    op.drop_index("ix_webhook_events_id", table_name="webhook_events")
    op.drop_table("webhook_events")

    op.drop_index("ix_web_broadcasts_broadcast_at", table_name="web_broadcasts")
    op.drop_index("ix_web_broadcasts_is_emergency", table_name="web_broadcasts")
    op.drop_index("ix_web_broadcasts_language", table_name="web_broadcasts")
    op.drop_index("ix_web_broadcasts_campaign_id", table_name="web_broadcasts")
    op.drop_index("ix_web_broadcasts_id", table_name="web_broadcasts")
    op.drop_table("web_broadcasts")

    op.drop_index("ix_device_tokens_is_active", table_name="device_tokens")
    op.drop_index("ix_device_tokens_device_type", table_name="device_tokens")
    op.drop_index("ix_device_tokens_user_id", table_name="device_tokens")
    op.drop_index("ix_device_tokens_audience_member_id", table_name="device_tokens")
    op.drop_index("ix_device_tokens_token", table_name="device_tokens")
    op.drop_index("ix_device_tokens_id", table_name="device_tokens")
    op.drop_table("device_tokens")
