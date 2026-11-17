"""Add campaign_schedules, automation_rules, automation_execution_logs, and retry tracking columns for Task 15.

Revision ID: e7a1b4c3d2e5
Revises: d6f9c3e2b5a1
Create Date: 2026-11-17 14:00:00.000000
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "e7a1b4c3d2e5"
down_revision: Union[str, None] = "d6f9c3e2b5a1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create campaign_schedules table
    op.create_table(
        "campaign_schedules",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("campaign_id", sa.Integer(), nullable=False, comment="Associated campaign"),
        sa.Column("schedule_type", sa.String(length=30), nullable=False, server_default="once", comment="once, daily, weekly"),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True, comment="Target future UTC timestamp"),
        sa.Column("recurrence_pattern", sa.String(length=50), nullable=True),
        sa.Column("recurrence_time", sa.String(length=10), nullable=True, comment="HH:MM in target timezone"),
        sa.Column("recurrence_days", postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), "sqlite"), nullable=True),
        sa.Column("timezone", sa.String(length=50), nullable=False, server_default="UTC"),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="active", comment="active, paused, completed, cancelled"),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("job_id", sa.String(length=100), nullable=True),
        sa.Column("execution_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("channels", postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), "sqlite"), nullable=True),
        sa.Column("fallback_order", postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), "sqlite"), nullable=True),
        sa.Column("enable_fallback", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("campaign_id", name="uq_campaign_schedules_campaign_id"),
    )
    op.create_index("ix_campaign_schedules_id", "campaign_schedules", ["id"], unique=False)
    op.create_index("ix_campaign_schedules_campaign_id", "campaign_schedules", ["campaign_id"], unique=True)
    op.create_index("ix_campaign_schedules_schedule_type", "campaign_schedules", ["schedule_type"], unique=False)
    op.create_index("ix_campaign_schedules_status", "campaign_schedules", ["status"], unique=False)
    op.create_index("ix_campaign_schedules_scheduled_at", "campaign_schedules", ["scheduled_at"], unique=False)
    op.create_index("ix_campaign_schedules_next_run_at", "campaign_schedules", ["next_run_at"], unique=False)
    op.create_index("ix_campaign_schedules_job_id", "campaign_schedules", ["job_id"], unique=False)

    # 2. Create automation_rules table
    op.create_table(
        "automation_rules",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("campaign_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("trigger_condition", sa.String(length=50), nullable=False, server_default="message_not_opened"),
        sa.Column("wait_hours", sa.Integer(), nullable=False, server_default="24"),
        sa.Column("wait_minutes", sa.Integer(), nullable=True),
        sa.Column("action_type", sa.String(length=50), nullable=False, server_default="send_reminder"),
        sa.Column("action_channel", sa.String(length=30), nullable=False, server_default="SMS"),
        sa.Column("custom_message", sa.Text(), nullable=True),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_automation_rules_id", "automation_rules", ["id"], unique=False)
    op.create_index("ix_automation_rules_campaign_id", "automation_rules", ["campaign_id"], unique=False)
    op.create_index("ix_automation_rules_trigger_condition", "automation_rules", ["trigger_condition"], unique=False)
    op.create_index("ix_automation_rules_is_enabled", "automation_rules", ["is_enabled"], unique=False)

    # 3. Create automation_execution_logs table
    op.create_table(
        "automation_execution_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("rule_id", sa.Integer(), nullable=False),
        sa.Column("campaign_id", sa.Integer(), nullable=False),
        sa.Column("message_id", sa.Integer(), nullable=False),
        sa.Column("audience_member_id", sa.Integer(), nullable=False),
        sa.Column("action_taken", sa.String(length=100), nullable=False),
        sa.Column("target_channel", sa.String(length=30), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="success"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("executed_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["rule_id"], ["automation_rules.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["message_id"], ["messages.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["audience_member_id"], ["audience_members.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("rule_id", "message_id", name="uq_automation_rule_message"),
    )
    op.create_index("ix_automation_execution_logs_id", "automation_execution_logs", ["id"], unique=False)
    op.create_index("ix_automation_execution_logs_rule_id", "automation_execution_logs", ["rule_id"], unique=False)
    op.create_index("ix_automation_execution_logs_campaign_id", "automation_execution_logs", ["campaign_id"], unique=False)
    op.create_index("ix_automation_execution_logs_message_id", "automation_execution_logs", ["message_id"], unique=False)
    op.create_index("ix_automation_execution_logs_audience_member_id", "automation_execution_logs", ["audience_member_id"], unique=False)
    op.create_index("ix_automation_execution_logs_executed_at", "automation_execution_logs", ["executed_at"], unique=False)

    # 4. Add retry and delivery tracking columns to messages
    op.add_column("messages", sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0", comment="Number of retries executed"))
    op.add_column("messages", sa.Column("max_retries", sa.Integer(), nullable=False, server_default="3", comment="Maximum allowed retries"))
    op.add_column("messages", sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True, comment="Next retry timestamp"))
    op.add_column("messages", sa.Column("opened_at", sa.DateTime(timezone=True), nullable=True, comment="Read or opened timestamp"))

    op.create_index("ix_messages_next_retry_at", "messages", ["next_retry_at"], unique=False)
    op.create_index("ix_messages_opened_at", "messages", ["opened_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_messages_opened_at", table_name="messages")
    op.drop_index("ix_messages_next_retry_at", table_name="messages")
    op.drop_column("messages", "opened_at")
    op.drop_column("messages", "next_retry_at")
    op.drop_column("messages", "max_retries")
    op.drop_column("messages", "retry_count")

    op.drop_index("ix_automation_execution_logs_executed_at", table_name="automation_execution_logs")
    op.drop_index("ix_automation_execution_logs_audience_member_id", table_name="automation_execution_logs")
    op.drop_index("ix_automation_execution_logs_message_id", table_name="automation_execution_logs")
    op.drop_index("ix_automation_execution_logs_campaign_id", table_name="automation_execution_logs")
    op.drop_index("ix_automation_execution_logs_rule_id", table_name="automation_execution_logs")
    op.drop_index("ix_automation_execution_logs_id", table_name="automation_execution_logs")
    op.drop_table("automation_execution_logs")

    op.drop_index("ix_automation_rules_is_enabled", table_name="automation_rules")
    op.drop_index("ix_automation_rules_trigger_condition", table_name="automation_rules")
    op.drop_index("ix_automation_rules_campaign_id", table_name="automation_rules")
    op.drop_index("ix_automation_rules_id", table_name="automation_rules")
    op.drop_table("automation_rules")

    op.drop_index("ix_campaign_schedules_job_id", table_name="campaign_schedules")
    op.drop_index("ix_campaign_schedules_next_run_at", table_name="campaign_schedules")
    op.drop_index("ix_campaign_schedules_scheduled_at", table_name="campaign_schedules")
    op.drop_index("ix_campaign_schedules_status", table_name="campaign_schedules")
    op.drop_index("ix_campaign_schedules_schedule_type", table_name="campaign_schedules")
    op.drop_index("ix_campaign_schedules_campaign_id", table_name="campaign_schedules")
    op.drop_index("ix_campaign_schedules_id", table_name="campaign_schedules")
    op.drop_table("campaign_schedules")
