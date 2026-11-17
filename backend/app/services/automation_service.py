"""Automated Workflows & Rules Engine.

Evaluates configured trigger conditions (e.g. IF message not opened within 24 hours,
THEN send reminder via another channel), enforces affirmative consent, prevents
infinite automation loops via execution deduplication, and records audit history.
"""

from __future__ import annotations
import uuid
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select, and_

from app.db.session import SessionLocal
from app.models.user import User
from app.models.campaign import Campaign
from app.models.communication import Message, DeliveryLog
from app.models.audience import AudienceMember
from app.models.automation_rule import AutomationRule, AutomationExecutionLog
from app.schemas.scheduling import (
    AutomationRuleCreateRequest,
    AutomationRuleUpdateRequest,
    AutomationRuleResponse,
    AutomationExecutionLogResponse,
)
from app.services.channels import get_configured_channel

logger = logging.getLogger("masscommai.automation")


def create_automation_rule(
    db: Session,
    campaign_id: int,
    payload: AutomationRuleCreateRequest,
    current_user: User,
) -> AutomationRuleResponse:
    """Creates a new automated workflow rule for a campaign."""
    campaign = db.get(Campaign, campaign_id)
    if not campaign:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Campaign #{campaign_id} not found.",
        )

    # Tenant check
    if not getattr(current_user, "is_superuser", False) and current_user.role != "Admin":
        if getattr(campaign.creator, "organization_id", None) != getattr(current_user, "organization_id", None):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Cannot configure automation rules for campaigns of another organization.",
            )

    rule = AutomationRule(
        campaign_id=campaign_id,
        name=payload.name.strip(),
        trigger_condition=payload.trigger_condition,
        wait_hours=payload.wait_hours,
        wait_minutes=payload.wait_minutes,
        action_type=payload.action_type,
        action_channel=payload.action_channel,
        custom_message=payload.custom_message,
        is_enabled=payload.is_enabled,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)

    logger.info("Automation rule '%s' created for Campaign #%d.", rule.name, campaign_id)
    return _build_rule_response(rule)


def list_automation_rules(
    db: Session,
    campaign_id: int,
) -> List[AutomationRuleResponse]:
    """Lists all automation rules for a campaign."""
    stmt = (
        select(AutomationRule)
        .where(AutomationRule.campaign_id == campaign_id)
        .order_by(AutomationRule.id.asc())
    )
    rules = db.execute(stmt).scalars().all()
    return [_build_rule_response(r) for r in rules]


def update_automation_rule(
    db: Session,
    rule_id: int,
    payload: AutomationRuleUpdateRequest,
    current_user: User,
) -> AutomationRuleResponse:
    """Updates an existing automation rule."""
    rule = db.get(AutomationRule, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail=f"Automation rule #{rule_id} not found.")

    if payload.name is not None:
        rule.name = payload.name.strip()
    if payload.trigger_condition is not None:
        rule.trigger_condition = payload.trigger_condition
    if payload.wait_hours is not None:
        rule.wait_hours = payload.wait_hours
    if payload.wait_minutes is not None:
        rule.wait_minutes = payload.wait_minutes
    if payload.action_type is not None:
        rule.action_type = payload.action_type
    if payload.action_channel is not None:
        rule.action_channel = payload.action_channel
    if payload.custom_message is not None:
        rule.custom_message = payload.custom_message
    if payload.is_enabled is not None:
        rule.is_enabled = payload.is_enabled

    db.commit()
    db.refresh(rule)
    return _build_rule_response(rule)


def delete_automation_rule(
    db: Session,
    rule_id: int,
    current_user: User,
) -> Dict[str, Any]:
    """Deletes an automation rule."""
    rule = db.get(AutomationRule, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail=f"Automation rule #{rule_id} not found.")

    db.delete(rule)
    db.commit()
    return {"status": "ok", "message": f"Automation rule #{rule_id} deleted."}


def get_automation_execution_history(
    db: Session,
    campaign_id: int,
) -> List[AutomationExecutionLogResponse]:
    """Retrieves execution audit logs for a campaign's automation rules."""
    stmt = (
        select(AutomationExecutionLog, AudienceMember)
        .join(AudienceMember, AutomationExecutionLog.audience_member_id == AudienceMember.id)
        .where(AutomationExecutionLog.campaign_id == campaign_id)
        .order_by(AutomationExecutionLog.executed_at.desc(), AutomationExecutionLog.id.desc())
    )
    results = db.execute(stmt).all()
    logs: List[AutomationExecutionLogResponse] = []
    for el, member in results:
        logs.append(
            AutomationExecutionLogResponse(
                id=el.id,
                rule_id=el.rule_id,
                campaign_id=el.campaign_id,
                message_id=el.message_id,
                audience_member_id=el.audience_member_id,
                recipient_name=member.name if member else "Citizen",
                action_taken=el.action_taken,
                target_channel=el.target_channel,
                status=el.status,
                error_message=el.error_message,
                executed_at=el.executed_at,
            )
        )
    return logs


async def evaluate_campaign_automation_rules(
    db: Session,
    campaign_id: int,
    simulated_now: Optional[datetime] = None,
) -> int:
    """
    Evaluates enabled automation rules for a campaign.
    Supports a simulated reference clock for testing 24-hour windows without waiting in real time.
    Returns the count of executed actions.
    """
    now_utc = simulated_now or datetime.now(timezone.utc)
    if now_utc.tzinfo is None:
        now_utc = now_utc.replace(tzinfo=timezone.utc)

    stmt_rules = (
        select(AutomationRule)
        .where(
            AutomationRule.campaign_id == campaign_id,
            AutomationRule.is_enabled == True,
        )
    )
    rules = db.execute(stmt_rules).scalars().all()
    if not rules:
        return 0

    executed_count = 0

    for rule in rules:
        # Determine effective waiting threshold
        if rule.wait_minutes is not None:
            wait_delta = timedelta(minutes=rule.wait_minutes)
        else:
            wait_delta = timedelta(hours=rule.wait_hours)

        cutoff_time = now_utc - wait_delta

        # Find candidate messages based on trigger condition
        if rule.trigger_condition == "message_not_opened":
            # Message was delivered before cutoff time and opened_at is still NULL
            stmt_msgs = (
                select(Message)
                .where(
                    Message.campaign_id == campaign_id,
                    Message.status.in_(["Delivered", "Sent"]),
                    Message.opened_at == None,
                    Message.delivered_at != None,
                    Message.delivered_at <= cutoff_time,
                )
            )
        elif rule.trigger_condition in ("message_delivery_failed", "message_not_delivered"):
            stmt_msgs = (
                select(Message)
                .where(
                    Message.campaign_id == campaign_id,
                    Message.status == "Failed",
                    Message.created_at <= cutoff_time,
                )
            )
        else:
            continue

        candidate_msgs = db.execute(stmt_msgs).scalars().all()

        for msg in candidate_msgs:
            # 1. Loop and duplicate prevention check
            stmt_log = select(AutomationExecutionLog).where(
                AutomationExecutionLog.rule_id == rule.id,
                AutomationExecutionLog.message_id == msg.id,
            )
            already_executed = db.execute(stmt_log).scalar_one_or_none()
            if already_executed:
                # Already processed for this message — strictly prevent infinite loops or repeated reminders
                continue

            member = msg.audience_member
            if not member:
                continue

            # 2. Strict affirmative consent verification for the target action channel
            if not member.consent_status:
                log_entry = AutomationExecutionLog(
                    rule_id=rule.id,
                    campaign_id=campaign_id,
                    message_id=msg.id,
                    audience_member_id=member.id,
                    action_taken=rule.action_type,
                    target_channel=rule.action_channel,
                    status="skipped",
                    error_message=f"Recipient {member.name} (#{member.id}) has not granted affirmative consent.",
                    executed_at=now_utc,
                )
                db.add(log_entry)
                db.commit()
                continue

            # 3. Determine recipient destination on the target action channel
            dest = member.phone if rule.action_channel in ("SMS", "WhatsApp") else member.email
            if not dest:
                log_entry = AutomationExecutionLog(
                    rule_id=rule.id,
                    campaign_id=campaign_id,
                    message_id=msg.id,
                    audience_member_id=member.id,
                    action_taken=rule.action_type,
                    target_channel=rule.action_channel,
                    status="skipped",
                    error_message=f"Missing address/phone for channel {rule.action_channel}.",
                    executed_at=now_utc,
                )
                db.add(log_entry)
                db.commit()
                continue

            # 4. Dispatch reminder message
            reminder_text = rule.custom_message or f"Reminder: {msg.rendered_content}"
            channel_adapter = get_configured_channel(db, rule.action_channel)

            class _AutomationMessagePayload:
                def __init__(self, body: str, tracking_id: str, subject: str):
                    self.rendered_content = body
                    self.body = body
                    self.tracking_id = tracking_id
                    self.subject = subject
                    self.title = subject

            reminder_payload = _AutomationMessagePayload(
                body=reminder_text,
                tracking_id=f"trk_{uuid.uuid4().hex[:16]}",
                subject=f"Reminder: {msg.campaign.name if msg.campaign else 'Important Notice'}",
            )

            send_result = await channel_adapter.send(
                message=reminder_payload,
                recipient=member,
            )

            # Record execution log
            log_status = "success" if send_result.success else "failed"
            log_entry = AutomationExecutionLog(
                rule_id=rule.id,
                campaign_id=campaign_id,
                message_id=msg.id,
                audience_member_id=member.id,
                action_taken=f"{rule.action_type}:{rule.action_channel}",
                target_channel=rule.action_channel,
                status=log_status,
                error_message=send_result.error_message if not send_result.success else None,
                executed_at=now_utc,
            )
            db.add(log_entry)

            # If send succeeded, persist a new Message record for tracking this reminder
            if send_result.success:
                new_msg = Message(
                    campaign_id=campaign_id,
                    audience_member_id=member.id,
                    template_id=msg.template_id,
                    content_asset_id=msg.content_asset_id,
                    content_variant_id=msg.content_variant_id,
                    channel=rule.action_channel,
                    language=msg.language,
                    rendered_content=reminder_text,
                    status=send_result.status,
                    provider_message_id=send_result.provider_message_id,
                    sent_at=now_utc,
                    delivered_at=now_utc if send_result.status == "Delivered" else None,
                )
                db.add(new_msg)
                db.flush()

                # Add delivery log
                d_log = DeliveryLog(
                    message_id=new_msg.id,
                    channel=rule.action_channel,
                    status=send_result.status,
                    error_message=None,
                    retry_count=0,
                )
                db.add(d_log)

            db.commit()
            executed_count += 1
            logger.info(
                "Automation rule #%d executed for message #%d (channel: %s, outcome: %s).",
                rule.id,
                msg.id,
                rule.action_channel,
                log_status,
            )

    return executed_count


async def process_all_automation_rules():
    """Periodic background worker checking automation rules across active campaigns."""
    with SessionLocal() as db:
        # Check campaigns in Running or Completed states with active rules
        stmt = (
            select(AutomationRule.campaign_id)
            .where(AutomationRule.is_enabled == True)
            .distinct()
        )
        campaign_ids = db.execute(stmt).scalars().all()
        for cid in campaign_ids:
            try:
                await evaluate_campaign_automation_rules(db, cid)
            except Exception as exc:
                logger.error("Error evaluating automation rules for campaign #%d: %s", cid, exc)


def _build_rule_response(rule: AutomationRule) -> AutomationRuleResponse:
    return AutomationRuleResponse(
        id=rule.id,
        campaign_id=rule.campaign_id,
        name=rule.name,
        trigger_condition=rule.trigger_condition,
        wait_hours=rule.wait_hours,
        wait_minutes=rule.wait_minutes,
        action_type=rule.action_type,
        action_channel=rule.action_channel,
        custom_message=rule.custom_message,
        is_enabled=rule.is_enabled,
        created_at=rule.created_at,
        updated_at=rule.updated_at,
    )
