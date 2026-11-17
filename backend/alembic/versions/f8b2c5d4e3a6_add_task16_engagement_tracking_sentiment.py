"""Add tracked_links, engagement_events, and feedback sentiment enhancement columns for Task 16.

Revision ID: f8b2c5d4e3a6
Revises: e7a1b4c3d2e5
Create Date: 2026-11-17 15:00:00.000000
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "f8b2c5d4e3a6"
down_revision: Union[str, None] = "e7a1b4c3d2e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create tracked_links table
    op.create_table(
        "tracked_links",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("link_id", sa.String(length=64), nullable=False, comment="Short public redirect identifier"),
        sa.Column("campaign_id", sa.Integer(), nullable=False, comment="Associated campaign"),
        sa.Column("message_id", sa.Integer(), nullable=True, comment="Associated message"),
        sa.Column("original_url", sa.String(length=2048), nullable=False, comment="Target redirect destination URL"),
        sa.Column("click_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("last_clicked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["message_id"], ["messages.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("link_id", name="uq_tracked_links_link_id"),
    )
    op.create_index(op.f("ix_tracked_links_id"), "tracked_links", ["id"], unique=False)
    op.create_index(op.f("ix_tracked_links_link_id"), "tracked_links", ["link_id"], unique=True)
    op.create_index(op.f("ix_tracked_links_campaign_id"), "tracked_links", ["campaign_id"], unique=False)
    op.create_index(op.f("ix_tracked_links_message_id"), "tracked_links", ["message_id"], unique=False)
    op.create_index(op.f("ix_tracked_links_is_active"), "tracked_links", ["is_active"], unique=False)

    # 2. Create engagement_events table
    op.create_table(
        "engagement_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("campaign_id", sa.Integer(), nullable=False, comment="Associated campaign"),
        sa.Column("message_id", sa.Integer(), nullable=True, comment="Associated message"),
        sa.Column("audience_member_id", sa.Integer(), nullable=True, comment="Associated citizen"),
        sa.Column("event_type", sa.String(length=30), nullable=False, comment="open, click, reply, participate"),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("device_info", sa.String(length=255), nullable=True, comment="Client user-agent or device classification"),
        sa.Column("language", sa.String(length=30), nullable=True, server_default="en"),
        sa.Column("link_url", sa.String(length=1000), nullable=True, comment="Target link for click events"),
        sa.Column(
            "metadata_json",
            postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), "sqlite"),
            nullable=True,
            comment="Extra context e.g. feedback details",
        ),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["message_id"], ["messages.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["audience_member_id"], ["audience_members.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_engagement_events_id"), "engagement_events", ["id"], unique=False)
    op.create_index(op.f("ix_engagement_events_campaign_id"), "engagement_events", ["campaign_id"], unique=False)
    op.create_index(op.f("ix_engagement_events_message_id"), "engagement_events", ["message_id"], unique=False)
    op.create_index(op.f("ix_engagement_events_audience_member_id"), "engagement_events", ["audience_member_id"], unique=False)
    op.create_index(op.f("ix_engagement_events_event_type"), "engagement_events", ["event_type"], unique=False)
    op.create_index(op.f("ix_engagement_events_timestamp"), "engagement_events", ["timestamp"], unique=False)
    op.create_index(
        "ix_engagement_events_campaign_type",
        "engagement_events",
        ["campaign_id", "event_type"],
        unique=False,
    )

    # 3. Add feedback_token column to messages
    op.add_column("messages", sa.Column("feedback_token", sa.String(length=64), nullable=True))
    op.create_index(op.f("ix_messages_feedback_token"), "messages", ["feedback_token"], unique=True)

    # 4. Add enhancement columns to feedback
    op.add_column("feedback", sa.Column("message_id", sa.Integer(), nullable=True))
    op.add_column("feedback", sa.Column("channel", sa.String(length=30), nullable=True, server_default="Web"))
    op.add_column("feedback", sa.Column("is_resolved", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.add_column("feedback", sa.Column("resolution_notes", sa.Text(), nullable=True))
    op.add_column("feedback", sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("feedback", sa.Column("feedback_token", sa.String(length=64), nullable=True))
    op.create_foreign_key("fk_feedback_message_id", "feedback", "messages", ["message_id"], ["id"], ondelete="SET NULL")
    op.create_index(op.f("ix_feedback_message_id"), "feedback", ["message_id"], unique=False)
    op.create_index(op.f("ix_feedback_is_resolved"), "feedback", ["is_resolved"], unique=False)
    op.create_index(op.f("ix_feedback_feedback_token"), "feedback", ["feedback_token"], unique=False)


def downgrade() -> None:
    # 4. Remove columns from feedback
    op.drop_constraint("fk_feedback_message_id", "feedback", type_="foreignkey")
    op.drop_index(op.f("ix_feedback_feedback_token"), table_name="feedback")
    op.drop_index(op.f("ix_feedback_is_resolved"), table_name="feedback")
    op.drop_index(op.f("ix_feedback_message_id"), table_name="feedback")
    op.drop_column("feedback", "feedback_token")
    op.drop_column("feedback", "resolved_at")
    op.drop_column("feedback", "resolution_notes")
    op.drop_column("feedback", "is_resolved")
    op.drop_column("feedback", "channel")
    op.drop_column("feedback", "message_id")

    # 3. Remove feedback_token from messages
    op.drop_index(op.f("ix_messages_feedback_token"), table_name="messages")
    op.drop_column("messages", "feedback_token")

    # 2. Drop engagement_events table
    op.drop_index("ix_engagement_events_campaign_type", table_name="engagement_events")
    op.drop_index(op.f("ix_engagement_events_timestamp"), table_name="engagement_events")
    op.drop_index(op.f("ix_engagement_events_event_type"), table_name="engagement_events")
    op.drop_index(op.f("ix_engagement_events_audience_member_id"), table_name="engagement_events")
    op.drop_index(op.f("ix_engagement_events_message_id"), table_name="engagement_events")
    op.drop_index(op.f("ix_engagement_events_campaign_id"), table_name="engagement_events")
    op.drop_index(op.f("ix_engagement_events_id"), table_name="engagement_events")
    op.drop_table("engagement_events")

    # 1. Drop tracked_links table
    op.drop_index(op.f("ix_tracked_links_is_active"), table_name="tracked_links")
    op.drop_index(op.f("ix_tracked_links_message_id"), table_name="tracked_links")
    op.drop_index(op.f("ix_tracked_links_campaign_id"), table_name="tracked_links")
    op.drop_index(op.f("ix_tracked_links_link_id"), table_name="tracked_links")
    op.drop_index(op.f("ix_tracked_links_id"), table_name="tracked_links")
    op.drop_table("tracked_links")
