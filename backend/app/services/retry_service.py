"""Retry Mechanism Service supporting manual and automated retry with a strict 3-attempt ceiling.

Ensures no successfully delivered message is retried, verifies affirmative recipient consent
at retry time, preserves retry history in DeliveryLog and fallback_attempts, and enforces
retry intervals between attempts.
"""

from __future__ import annotations
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any, Tuple

from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select, and_

from app.db.session import SessionLocal
from app.models.user import User
from app.models.campaign import Campaign
from app.models.communication import Message, DeliveryLog
from app.models.audience import AudienceMember
from app.schemas.scheduling import (
    MessageRetryResponse,
    RetryBatchResponse,
)
from app.services.channels import get_configured_channel

logger = logging.getLogger("masscommai.retry_service")

# Configurable retry parameters
MAX_RETRY_ATTEMPTS = 3
DEFAULT_RETRY_GAP_MINUTES = 5


async def retry_single_message(
    db: Session,
    message_id: int,
    current_user: Optional[User] = None,
    force: bool = False,
    simulated_now: Optional[datetime] = None,
) -> MessageRetryResponse:
    """
    Retries an individual message with safety checks:
    1. Rejects if message status is already 'Delivered'.
    2. Rejects if retry_count >= max_retries (ceiling of 3 attempts).
    3. Rejects if retry gap interval has not elapsed (unless force=True).
    4. Validates affirmative recipient consent.
    5. Dispatches via channel adapter, records attempt history, and updates status.
    """
    msg = db.get(Message, message_id)
    if not msg:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Message #{message_id} not found.",
        )

    # 1. Do not retry successfully delivered messages
    if msg.status == "Delivered":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Message #{message_id} is already Delivered. Successful messages cannot be retried.",
        )

    # 2. Strict maximum 3 attempts ceiling
    if msg.retry_count >= msg.max_retries:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Message #{message_id} has reached the maximum allowed retry attempts "
                f"({msg.retry_count}/{msg.max_retries}). Manual retry disallowed."
            ),
        )

    now_utc = simulated_now or datetime.now(timezone.utc)
    if now_utc.tzinfo is None:
        now_utc = now_utc.replace(tzinfo=timezone.utc)

    # 3. Check retry interval if next_retry_at is in the future
    next_retry = msg.next_retry_at
    if next_retry and next_retry.tzinfo is None:
        next_retry = next_retry.replace(tzinfo=timezone.utc)

    if not force and next_retry and next_retry > now_utc:
        diff_secs = int((next_retry - now_utc).total_seconds())
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Retry interval in effect. Please wait {diff_secs} seconds before retrying.",
        )

    # 4. Consent check at execution time
    member = msg.audience_member
    if not member or not member.consent_status:
        msg.failure_reason = "Recipient consent revoked or missing."
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot retry message: Recipient consent is not granted.",
        )

    # Destination address
    dest = (
        (member.phone if msg.channel in ("SMS", "WhatsApp") else member.email)
        if member
        else ""
    )
    if not dest:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Recipient #{member.id} has no valid address for channel '{msg.channel}'.",
        )

    prev_status = msg.status
    msg.retry_count += 1

    # Record retry attempt in fallback_attempts audit trail
    attempts = list(msg.fallback_attempts or [])
    attempts.append({
        "attempt_type": "retry",
        "retry_number": msg.retry_count,
        "channel": msg.channel,
        "timestamp": now_utc.isoformat(),
    })
    msg.fallback_attempts = attempts

    # 5. Dispatch via configured channel
    channel_adapter = get_configured_channel(db, msg.channel)

    class _RetryMessagePayload:
        def __init__(self, m: Message):
            self.id = m.id
            self.rendered_content = m.rendered_content
            self.body = m.rendered_content
            self.tracking_id = m.tracking_id
            self.channel = m.channel
            self.language = m.language
            self.subject = getattr(m, "subject", None) or (f"Notice: {m.campaign.name}" if getattr(m, "campaign", None) else "Civora")
            self.title = self.subject

    retry_payload = _RetryMessagePayload(msg)
    send_result = await channel_adapter.send(
        message=retry_payload,
        recipient=member,
    )

    if send_result.success:
        msg.status = send_result.status
        msg.provider_message_id = send_result.provider_message_id
        msg.sent_at = now_utc
        if send_result.status == "Delivered":
            msg.delivered_at = now_utc
        msg.failure_reason = None
        msg.next_retry_at = None
        detail_msg = f"Retry attempt {msg.retry_count} succeeded with status '{send_result.status}'."
    else:
        msg.status = "Failed"
        msg.failure_reason = send_result.error_message or "Retry delivery failed"
        # Schedule next retry if still under ceiling
        if msg.retry_count < msg.max_retries:
            msg.next_retry_at = now_utc + timedelta(minutes=DEFAULT_RETRY_GAP_MINUTES)
        else:
            msg.next_retry_at = None
        detail_msg = f"Retry attempt {msg.retry_count} failed: {msg.failure_reason}"

    # DeliveryLog entry
    d_log = DeliveryLog(
        message_id=msg.id,
        channel=msg.channel,
        status=msg.status,
        error_message=msg.failure_reason,
        retry_count=msg.retry_count,
    )
    db.add(d_log)
    db.commit()
    db.refresh(msg)

    logger.info("Message #%d retry completed: %s", msg.id, detail_msg)

    return MessageRetryResponse(
        message_id=msg.id,
        tracking_id=msg.tracking_id,
        previous_status=prev_status,
        new_status=msg.status,
        retry_count=msg.retry_count,
        max_retries=msg.max_retries,
        channel_attempted=msg.channel,
        success=send_result.success,
        detail=detail_msg,
    )


async def retry_failed_messages(
    db: Session,
    campaign_id: Optional[int] = None,
    current_user: Optional[User] = None,
    force: bool = True,
) -> RetryBatchResponse:
    """
    Retries all eligible failed messages for a campaign or across campaigns.
    Skips delivered, over-limit, or unconsented messages.
    """
    stmt = (
        select(Message)
        .where(
            Message.status == "Failed",
            Message.retry_count < Message.max_retries,
        )
    )
    if campaign_id:
        stmt = stmt.where(Message.campaign_id == campaign_id)

    failed_msgs = db.execute(stmt).scalars().all()
    total_eligible = len(failed_msgs)

    details: List[MessageRetryResponse] = []
    succeeded_count = 0
    retried_count = 0
    failed_count = 0
    skipped_count = 0

    for msg in failed_msgs:
        # Consent check
        if not msg.audience_member or not msg.audience_member.consent_status:
            skipped_count += 1
            continue

        try:
            res = await retry_single_message(
                db=db,
                message_id=msg.id,
                current_user=current_user,
                force=force,
            )
            retried_count += 1
            if res.success:
                succeeded_count += 1
            else:
                failed_count += 1
            details.append(res)
        except Exception as exc:
            logger.warning("Error retrying message #%d: %s", msg.id, exc)
            failed_count += 1

    return RetryBatchResponse(
        total_eligible=total_eligible,
        retried_count=retried_count,
        succeeded_count=succeeded_count,
        failed_count=failed_count,
        skipped_count=skipped_count,
        details=details,
    )


async def process_automatic_retries():
    """
    Background worker invoked periodically by APScheduler.
    Queries all failed messages where retry_count < max_retries and next_retry_at <= now_utc.
    Automatically executes retry.
    """
    now_utc = datetime.now(timezone.utc)
    with SessionLocal() as db:
        stmt = (
            select(Message)
            .where(
                Message.status == "Failed",
                Message.retry_count < Message.max_retries,
                Message.next_retry_at != None,
                Message.next_retry_at <= now_utc,
            )
            .limit(50)
        )
        eligible = db.execute(stmt).scalars().all()
        if eligible:
            logger.info("Automatic retry worker found %d eligible failed message(s).", len(eligible))
            for msg in eligible:
                try:
                    await retry_single_message(db=db, message_id=msg.id, force=True)
                except Exception as exc:
                    logger.error("Auto-retry error for message #%d: %s", msg.id, exc)
