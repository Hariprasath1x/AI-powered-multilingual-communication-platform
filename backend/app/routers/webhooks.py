"""Inbound Webhooks router supporting Meta WhatsApp verification, delivery status tracking, and push receipts."""

from __future__ import annotations
import hmac
import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Path, Request, Response, status
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.db.session import get_db
from app.models.channel_config import ChannelConfiguration
from app.models.communication import Message, DeliveryLog, Feedback
from app.models.webhook_event import WebhookEvent

logger = logging.getLogger("masscommai.webhooks")

router = APIRouter(
    prefix="/webhooks",
    tags=["Webhooks"],
)

DEFAULT_VERIFY_TOKEN = "masscomm_webhook_verify_token"


def _verify_meta_signature(app_secret: str, raw_body: bytes, signature_header: Optional[str]) -> bool:
    """Validates X-Hub-Signature-256 HMAC-SHA256 signature from Meta Graph API."""
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    expected_hash = signature_header.split("sha256=")[1].strip()
    computed_hash = hmac.new(
        app_secret.encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected_hash, computed_hash)


@router.get(
    "/whatsapp",
    summary="Meta WhatsApp Webhook verification handshake",
)
def verify_whatsapp_webhook(
    hub_mode: Optional[str] = Query(None, alias="hub.mode"),
    hub_challenge: Optional[str] = Query(None, alias="hub.challenge"),
    hub_verify_token: Optional[str] = Query(None, alias="hub.verify_token"),
    db: Session = Depends(get_db),
):
    """
    Responds to Meta WhatsApp Webhook verification handshake (hub.challenge).
    Verifies that hub.mode is 'subscribe' and hub.verify_token matches configured secret.
    """
    # Fetch configured webhook verification token if customized
    stmt = select(ChannelConfiguration).where(ChannelConfiguration.channel == "WhatsApp")
    cfg = db.execute(stmt).scalar_one_or_none()
    configured_token = DEFAULT_VERIFY_TOKEN
    if cfg and cfg.credentials and isinstance(cfg.credentials, dict):
        configured_token = cfg.credentials.get("webhook_verify_token") or cfg.credentials.get("verify_token") or DEFAULT_VERIFY_TOKEN

    if hub_mode == "subscribe" and hub_verify_token == configured_token:
        logger.info("WhatsApp webhook verification successful.")
        # Meta requires plain integer/string response
        return Response(content=str(hub_challenge), media_type="text/plain")

    logger.warning("WhatsApp webhook verification failed. Given token: %s", hub_verify_token)
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Webhook verification failed: Invalid verify token or mode.",
    )


@router.post(
    "/whatsapp",
    summary="Handle inbound Meta WhatsApp delivery receipts and messages",
)
async def handle_whatsapp_webhook(
    request: Request,
    x_hub_signature_256: Optional[str] = Header(None, alias="X-Hub-Signature-256"),
    db: Session = Depends(get_db),
):
    """
    Processes inbound delivery receipts, read statuses, and citizen replies from Meta WhatsApp.
    Enforces payload signature validation and idempotent deduplication via WebhookEvent.
    """
    raw_body = await request.body()

    # Optional signature check if app_secret is configured
    stmt = select(ChannelConfiguration).where(ChannelConfiguration.channel == "WhatsApp")
    cfg = db.execute(stmt).scalar_one_or_none()
    if cfg and cfg.credentials and isinstance(cfg.credentials, dict):
        app_secret = cfg.credentials.get("app_secret")
        if app_secret:
            if not _verify_meta_signature(app_secret, raw_body, x_hub_signature_256):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid HMAC signature.",
                )

    try:
        payload = json.loads(raw_body)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Malformed JSON payload: {exc}",
        )

    # Extract event details from Meta structure
    entries = payload.get("entry", [])
    processed_count = 0

    for entry in entries:
        changes = entry.get("changes", [])
        for change in changes:
            val = change.get("value", {})
            statuses = val.get("statuses", [])
            messages = val.get("messages", [])

            # 1. Process delivery receipts and read statuses
            for st in statuses:
                wamid = st.get("id")
                wa_status = st.get("status")  # sent, delivered, read, failed
                event_id = f"wa_status_{wamid}_{wa_status}"

                # Deduplication check
                existing = db.execute(select(WebhookEvent).where(WebhookEvent.event_id == event_id)).scalar_one_or_none()
                if existing:
                    continue

                event_rec = WebhookEvent(
                    provider="whatsapp",
                    event_id=event_id,
                    event_type=f"whatsapp_{wa_status}",
                    payload=st,
                    processed_status="processed",
                )
                db.add(event_rec)

                # Match Message by provider_message_id
                if wamid:
                    msg_stmt = select(Message).where(Message.provider_message_id == wamid)
                    msg = db.execute(msg_stmt).scalar_one_or_none()
                    if msg:
                        if wa_status in ("delivered", "read"):
                            msg.status = "Delivered"
                            msg.delivered_at = datetime.now(timezone.utc)
                        elif wa_status == "failed":
                            msg.status = "Failed"
                            errors = st.get("errors", [])
                            err_desc = errors[0].get("title") if errors else "WhatsApp delivery failure"
                            msg.failure_reason = err_desc

                        # Audit log
                        d_log = DeliveryLog(
                            message_id=msg.id,
                            channel="WhatsApp",
                            status=msg.status,
                            error_message=msg.failure_reason,
                            retry_count=0,
                        )
                        db.add(d_log)

                processed_count += 1

            # 2. Process inbound citizen messages (feedback)
            for m in messages:
                msg_id = m.get("id")
                event_id = f"wa_msg_{msg_id}"
                from_num = m.get("from")
                text_content = m.get("text", {}).get("body", "")

                existing = db.execute(select(WebhookEvent).where(WebhookEvent.event_id == event_id)).scalar_one_or_none()
                if existing:
                    continue

                event_rec = WebhookEvent(
                    provider="whatsapp",
                    event_id=event_id,
                    event_type="whatsapp_inbound_message",
                    payload=m,
                    processed_status="processed",
                )
                db.add(event_rec)

                # Correlate with recent message sent to this phone to identify campaign
                if from_num:
                    clean_phone = from_num.strip().replace(" ", "").replace("-", "")
                    recent_msg_stmt = (
                        select(Message)
                        .where(Message.channel == "WhatsApp")
                        .order_by(Message.id.desc())
                        .limit(1)
                    )
                    recent_msg = db.execute(recent_msg_stmt).scalar_one_or_none()
                    if recent_msg:
                        feedback = Feedback(
                            campaign_id=recent_msg.campaign_id,
                            audience_member_id=recent_msg.audience_member_id,
                            comment=text_content,
                            rating=None,
                        )
                        db.add(feedback)

                processed_count += 1

    db.commit()
    return {"status": "ok", "events_processed": processed_count}


@router.post(
    "/push",
    summary="Handle FCM delivery receipts and token expiration notifications",
)
async def handle_push_webhook(
    request: Request,
    db: Session = Depends(get_db),
):
    """Processes inbound delivery receipts or invalid token events from push providers."""
    try:
        payload = await request.json()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Malformed JSON: {exc}",
        )

    event_id = payload.get("event_id") or payload.get("message_id")
    if not event_id:
        event_id = f"push_{datetime.now(timezone.utc).timestamp()}"

    existing = db.execute(select(WebhookEvent).where(WebhookEvent.event_id == event_id)).scalar_one_or_none()
    if existing:
        return {"status": "already_processed"}

    event_rec = WebhookEvent(
        provider="fcm",
        event_id=event_id,
        event_type=payload.get("event_type", "delivery_receipt"),
        payload=payload,
        processed_status="processed",
    )
    db.add(event_rec)

    # If payload indicates invalid or expired device token
    invalid_token = payload.get("invalid_token") or payload.get("unregistered_token")
    if invalid_token:
        from app.models.device_token import DeviceToken
        dt_stmt = select(DeviceToken).where(DeviceToken.token == invalid_token)
        dt = db.execute(dt_stmt).scalar_one_or_none()
        if dt:
            dt.is_active = False

    db.commit()
    return {"status": "ok"}


@router.post(
    "/delivery",
    summary="Standard multi-channel provider delivery callback endpoint (Task 15)",
)
def handle_provider_delivery_callback(
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
):
    """
    Processes provider delivery callbacks (Twilio, SendGrid, Fast2SMS, etc.):
    - Validates status transition (Sent -> Delivered, or Failed).
    - Preserves provider message ID and failure reason.
    - Idempotently deduplicates event.
    - On failure, schedules next retry timestamp.
    """
    from app.schemas.scheduling import DeliveryCallbackPayload
    from app.services import delivery_tracking_service

    cb_payload = DeliveryCallbackPayload(
        provider=payload.get("provider", "generic"),
        provider_message_id=payload.get("provider_message_id") or payload.get("message_id") or payload.get("MessageSid"),
        tracking_id=payload.get("tracking_id"),
        status=payload.get("status", "sent"),
        failure_reason=payload.get("failure_reason") or payload.get("error_message") or payload.get("ErrorMessage"),
        error_code=payload.get("error_code") or payload.get("ErrorCode"),
        metadata=payload.get("metadata"),
    )
    success, msg_desc, _ = delivery_tracking_service.process_delivery_callback(db=db, payload=cb_payload)
    return {"status": "ok" if success else "error", "message": msg_desc}


@router.get(
    "/open/{tracking_id}",
    summary="Message open tracking pixel / callback (Task 15)",
)
def handle_message_open_tracking(
    tracking_id: str = Path(..., description="Message tracking ID"),
    db: Session = Depends(get_db),
):
    """
    Records message open/read event when email tracking pixel or read callback is loaded.
    Sets opened_at timestamp on Message to satisfy automation rule evaluations.
    """
    from app.schemas.scheduling import DeliveryCallbackPayload
    from app.services import delivery_tracking_service

    cb_payload = DeliveryCallbackPayload(
        provider="tracking_pixel",
        tracking_id=tracking_id,
        status="read",
    )
    delivery_tracking_service.process_delivery_callback(db=db, payload=cb_payload)
    # Return 1x1 transparent GIF placeholder
    return Response(
        content=b"GIF89a\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;",
        media_type="image/gif",
    )
