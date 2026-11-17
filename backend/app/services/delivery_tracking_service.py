"""Delivery Tracking Service managing provider delivery status callbacks, status transitions, and audit records."""

from __future__ import annotations
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any, Tuple

from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select, func, or_

from app.models.campaign import Campaign
from app.models.communication import Message, DeliveryLog
from app.models.audience import AudienceMember
from app.models.webhook_event import WebhookEvent
from app.schemas.scheduling import (
    DeliveryCallbackPayload,
    DeliveryTrackingSummaryResponse,
    FailedMessageItem,
    FailedMessagesListResponse,
)
from app.services.distribution.base import mask_recipient_address

logger = logging.getLogger("masscommai.delivery_tracking")

# Retry gap constant (5 minutes between retry attempts)
DEFAULT_RETRY_INTERVAL_MINUTES = 5


def process_delivery_callback(
    db: Session,
    payload: DeliveryCallbackPayload,
) -> Tuple[bool, str, Optional[Message]]:
    """
    Processes a provider delivery status callback:
    1. Idempotently deduplicates event using provider + provider_message_id/tracking_id + status.
    2. Finds Message by tracking_id or provider_message_id.
    3. Validates status transition (Queued -> Sent -> Delivered, or Failed).
    4. Sets timestamps (delivered_at, opened_at, sent_at).
    5. On failure, calculates next_retry_at if retry_count < max_retries.
    6. Appends DeliveryLog audit record and WebhookEvent.
    """
    prov = (payload.provider or "generic").lower()
    p_status = (payload.status or "sent").lower()
    key_id = payload.provider_message_id or payload.tracking_id or "unknown"
    event_id = f"cb_{prov}_{key_id}_{p_status}"

    # 1. Deduplication check
    existing_evt = db.execute(
        select(WebhookEvent).where(WebhookEvent.event_id == event_id)
    ).scalar_one_or_none()
    if existing_evt:
        logger.info("Duplicate callback received: %s. Returning idempotent success.", event_id)
        return True, "Duplicate event already processed.", None

    # Record webhook event
    evt_rec = WebhookEvent(
        provider=prov,
        event_id=event_id,
        event_type=f"delivery_callback_{p_status}",
        payload=payload.model_dump(),
        processed_status="processed",
    )
    db.add(evt_rec)

    # 2. Correlate with Message
    msg: Optional[Message] = None
    if payload.tracking_id:
        msg = db.execute(
            select(Message).where(Message.tracking_id == payload.tracking_id)
        ).scalar_one_or_none()
    if not msg and payload.provider_message_id:
        msg = db.execute(
            select(Message).where(Message.provider_message_id == payload.provider_message_id)
        ).scalar_one_or_none()

    if not msg:
        db.commit()
        logger.warning("No message matched for callback: %s", key_id)
        return True, "Callback recorded, but no matching message found in database.", None

    now_utc = payload.timestamp or datetime.now(timezone.utc)
    if now_utc.tzinfo is None:
        now_utc = now_utc.replace(tzinfo=timezone.utc)

    # 3. Status transitions
    if p_status in ("read", "opened"):
        msg.opened_at = now_utc
        # If not already marked Delivered, set it
        if msg.status != "Delivered":
            msg.status = "Delivered"
            msg.delivered_at = now_utc

    elif p_status in ("delivered", "received"):
        msg.status = "Delivered"
        msg.delivered_at = now_utc

    elif p_status in ("sent", "dispatched", "accepted"):
        # Provider accepted / in-flight: Do NOT mark as Delivered
        if msg.status != "Delivered":
            msg.status = "Sent"
            if not msg.sent_at:
                msg.sent_at = now_utc

    elif p_status in ("failed", "bounced", "undelivered", "rejected"):
        msg.status = "Failed"
        msg.failure_reason = payload.failure_reason or payload.error_code or "Provider delivery failed"

        # Calculate next retry time if eligible
        if msg.retry_count < msg.max_retries:
            msg.next_retry_at = now_utc + timedelta(minutes=DEFAULT_RETRY_INTERVAL_MINUTES)
        else:
            msg.next_retry_at = None

    if payload.provider_message_id and not msg.provider_message_id:
        msg.provider_message_id = payload.provider_message_id

    # 4. Audit Log entry
    log_entry = DeliveryLog(
        message_id=msg.id,
        channel=msg.channel,
        status=msg.status,
        error_message=msg.failure_reason if msg.status == "Failed" else None,
        retry_count=msg.retry_count,
    )
    db.add(log_entry)
    db.commit()
    db.refresh(msg)

    logger.info("Message #%d updated to status '%s' via provider callback.", msg.id, msg.status)
    return True, f"Status updated to '{msg.status}'.", msg


def get_campaign_delivery_summary(
    db: Session,
    campaign_id: int,
) -> DeliveryTrackingSummaryResponse:
    """Computes delivery tracking statistics for a campaign."""
    campaign = db.get(Campaign, campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found.")

    stmt = select(Message).where(Message.campaign_id == campaign_id)
    messages = db.execute(stmt).scalars().all()

    total = len(messages)
    sent = 0
    delivered = 0
    failed = 0
    pending = 0
    opened = 0
    retried = 0

    channel_stats: Dict[str, Dict[str, int]] = {}
    failure_reasons: Dict[str, int] = {}

    for m in messages:
        ch = m.channel or "Email"
        if ch not in channel_stats:
            channel_stats[ch] = {"total": 0, "sent": 0, "delivered": 0, "failed": 0, "opened": 0}
        channel_stats[ch]["total"] += 1

        if m.status == "Delivered":
            delivered += 1
            channel_stats[ch]["delivered"] += 1
        elif m.status == "Sent":
            sent += 1
            channel_stats[ch]["sent"] += 1
        elif m.status == "Failed":
            failed += 1
            channel_stats[ch]["failed"] += 1
            reason = (m.failure_reason or "Unknown failure").strip()[:80]
            failure_reasons[reason] = failure_reasons.get(reason, 0) + 1
        else:
            pending += 1

        if m.opened_at is not None:
            opened += 1
            channel_stats[ch]["opened"] += 1

        if m.retry_count > 0:
            retried += 1

    return DeliveryTrackingSummaryResponse(
        campaign_id=campaign.id,
        campaign_name=campaign.name,
        campaign_status=campaign.status,
        total_messages=total,
        sent_count=sent,
        delivered_count=delivered,
        failed_count=failed,
        pending_count=pending,
        opened_count=opened,
        retried_count=retried,
        channel_breakdown=channel_stats,
        failure_reasons=failure_reasons,
        last_updated=datetime.now(timezone.utc),
    )


def list_failed_messages(
    db: Session,
    campaign_id: Optional[int] = None,
    channel: Optional[str] = None,
    page: int = 1,
    page_size: int = 50,
) -> FailedMessagesListResponse:
    """Retrieves list of failed messages with retry eligibility."""
    stmt = (
        select(Message, Campaign, AudienceMember)
        .join(Campaign, Message.campaign_id == Campaign.id)
        .join(AudienceMember, Message.audience_member_id == AudienceMember.id)
        .where(Message.status == "Failed")
        .order_by(Message.updated_at.desc(), Message.id.desc())
    )
    if campaign_id:
        stmt = stmt.where(Message.campaign_id == campaign_id)
    if channel:
        stmt = stmt.where(Message.channel == channel)

    total_count = len(db.execute(stmt).all())
    results = db.execute(stmt.offset((page - 1) * page_size).limit(page_size)).all()

    items: List[FailedMessageItem] = []
    for msg, camp, member in results:
        addr = ""
        if msg.channel in ("SMS", "WhatsApp"):
            addr = member.phone or ""
        elif msg.channel == "Email":
            addr = member.email or ""
        else:
            addr = "web-broadcast"

        can_retry = (msg.retry_count < msg.max_retries) and (member.consent_status == True)

        items.append(
            FailedMessageItem(
                id=msg.id,
                tracking_id=msg.tracking_id,
                campaign_id=camp.id,
                campaign_name=camp.name,
                recipient_id=member.id,
                recipient_name=member.name,
                recipient_address=mask_recipient_address(addr),
                channel=msg.channel,
                language=msg.language,
                status=msg.status,
                retry_count=msg.retry_count,
                max_retries=msg.max_retries,
                can_retry=can_retry,
                failure_reason=msg.failure_reason,
                fallback_attempts=msg.fallback_attempts or [],
                created_at=msg.created_at,
                updated_at=msg.updated_at,
            )
        )

    return FailedMessagesListResponse(total=total_count, items=items)
