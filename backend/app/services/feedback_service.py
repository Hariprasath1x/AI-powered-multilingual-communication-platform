"""Citizen Feedback Collection and Resolution Service.

Provides:
1. Public token validation and zero-PII metadata disclosure for feedback forms.
2. Secure citizen feedback ingestion with duplicate submission protection.
3. Automated sentiment classification and continuous scoring on comments.
4. Administrative feedback triage, resolution workflow, and authorized reply dispatch.
"""

from __future__ import annotations
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Tuple

from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select, func, and_

from app.models.user import User
from app.models.campaign import Campaign
from app.models.communication import Message, Feedback, DeliveryLog
from app.models.audience import AudienceMember
from app.models.engagement import EngagementEvent
from app.schemas.engagement import (
    PublicFeedbackSubmissionRequest,
    PublicFeedbackInfoResponse,
    FeedbackResponse,
    FeedbackDetailResponse,
    FeedbackListResponse,
    FeedbackReplyResponse,
)
from app.services import sentiment_service
from app.services.channels import get_configured_channel

logger = logging.getLogger("masscommai.feedback")


def mask_contact(contact: Optional[str]) -> str:
    """Masks email or phone number for privacy preservation."""
    if not contact:
        return ""
    val = contact.strip()
    if "@" in val:
        parts = val.split("@")
        name, domain = parts[0], parts[1]
        visible = name[:2] + "***" if len(name) > 2 else name[:1] + "***"
        return f"{visible}@{domain}"
    if len(val) >= 7:
        return val[:3] + "****" + val[-3:]
    return "***"


def get_public_feedback_info(db: Session, token: str) -> PublicFeedbackInfoResponse:
    """
    Validates a feedback token or message tracking ID and returns campaign context
    safe for public display without leaking citizen personal identity.
    """
    if not token or not token.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Feedback token is required.",
        )

    clean_token = token.strip()
    stmt = select(Message).where(
        (Message.feedback_token == clean_token) | (Message.tracking_id == clean_token)
    )
    msg = db.execute(stmt).scalar_one_or_none()

    if not msg:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invalid or expired feedback link.",
        )

    camp = msg.campaign
    return PublicFeedbackInfoResponse(
        campaign_id=camp.id,
        campaign_name=camp.name,
        campaign_objective=camp.objective or f"Citizen communication regarding {camp.name}",
        feedback_token=clean_token,
        preferred_language=msg.language or "en",
        channels=camp.channels if isinstance(camp.channels, list) else ["Email", "SMS"],
    )


def submit_public_feedback(
    db: Session,
    payload: PublicFeedbackSubmissionRequest,
    user_agent: Optional[str] = None,
) -> FeedbackResponse:
    """
    Submits public citizen feedback associated with a valid message/campaign token.
    Applies sentiment analysis to comments and records a 'participate' engagement event.
    Enforces duplicate-submission prevention per token.
    """
    clean_token = payload.feedback_token.strip()
    stmt = select(Message).where(
        (Message.feedback_token == clean_token) | (Message.tracking_id == clean_token)
    )
    msg = db.execute(stmt).scalar_one_or_none()

    if not msg:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invalid or expired feedback token.",
        )

    # Duplicate check: check if feedback already submitted for this message
    existing_stmt = select(Feedback).where(Feedback.message_id == msg.id)
    existing = db.execute(existing_stmt).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Feedback has already been submitted for this notification. Thank you!",
        )

    # Sentiment analysis on comment
    sentiment_label, sentiment_score = sentiment_service.analyze_sentiment(
        text=payload.comment,
        language=payload.language or msg.language or "en",
    )

    now_utc = datetime.now(timezone.utc)
    fb = Feedback(
        campaign_id=msg.campaign_id,
        audience_member_id=msg.audience_member_id,
        message_id=msg.id,
        channel=msg.channel or "Web",
        rating=payload.rating,
        comment=payload.comment.strip() if payload.comment else None,
        sentiment_label=sentiment_label,
        sentiment_score=sentiment_score,
        language=payload.language or msg.language or "en",
        is_resolved=False,
        feedback_token=clean_token,
        created_at=now_utc,
    )
    db.add(fb)
    db.flush()

    # Record 'participate' engagement event
    from app.services.link_tracking_service import parse_device_info
    device = parse_device_info(user_agent)

    event = EngagementEvent(
        campaign_id=msg.campaign_id,
        message_id=msg.id,
        audience_member_id=msg.audience_member_id,
        event_type="participate",
        timestamp=now_utc,
        device_info=device,
        language=fb.language,
        metadata_json={
            "feedback_id": fb.id,
            "rating": fb.rating,
            "sentiment_label": sentiment_label,
            "sentiment_score": sentiment_score,
        },
    )
    db.add(event)
    db.commit()
    db.refresh(fb)

    logger.info("Feedback #%d submitted for Campaign #%d (Sentiment: %s, Score: %.2f)",
                fb.id, msg.campaign_id, sentiment_label, sentiment_score)

    return FeedbackResponse.model_validate(fb)


def list_feedback(
    db: Session,
    campaign_id: Optional[int] = None,
    sentiment: Optional[str] = None,
    channel: Optional[str] = None,
    language: Optional[str] = None,
    is_resolved: Optional[bool] = None,
    limit: int = 50,
    offset: int = 0,
) -> FeedbackListResponse:
    """Queries feedback records with administrative filters and aggregate summary counts."""
    conditions = []
    if campaign_id is not None:
        conditions.append(Feedback.campaign_id == campaign_id)
    if sentiment:
        conditions.append(func.lower(Feedback.sentiment_label) == sentiment.lower().strip())
    if channel:
        conditions.append(func.lower(Feedback.channel) == channel.lower().strip())
    if language:
        conditions.append(func.lower(Feedback.language) == language.lower().strip())
    if is_resolved is not None:
        conditions.append(Feedback.is_resolved == is_resolved)

    base_query = select(Feedback).where(and_(*conditions)) if conditions else select(Feedback)

    # Total count
    total_stmt = select(func.count(Feedback.id)).where(and_(*conditions)) if conditions else select(func.count(Feedback.id))
    total = db.execute(total_stmt).scalar() or 0

    # Fetch items with pagination
    items_stmt = base_query.order_by(Feedback.id.desc()).offset(offset).limit(limit)
    rows = list(db.execute(items_stmt).scalars().all())

    # Aggregates across filtered domain
    pos_stmt = select(func.count(Feedback.id)).where(and_(*(conditions + [Feedback.sentiment_label == "Positive"])))
    neu_stmt = select(func.count(Feedback.id)).where(and_(*(conditions + [Feedback.sentiment_label == "Neutral"])))
    neg_stmt = select(func.count(Feedback.id)).where(and_(*(conditions + [Feedback.sentiment_label == "Negative"])))
    avg_stmt = select(func.avg(Feedback.rating)).where(and_(*(conditions + [Feedback.rating != None])))

    pos_cnt = db.execute(pos_stmt).scalar() or 0
    neu_cnt = db.execute(neu_stmt).scalar() or 0
    neg_cnt = db.execute(neg_stmt).scalar() or 0
    avg_rating = db.execute(avg_stmt).scalar() or 0.0

    items_out = []
    for f in rows:
        member = f.audience_member
        recip_name = member.name if member else "Anonymous Citizen"
        raw_contact = (member.email or member.phone or "") if member else ""
        masked_contact = mask_contact(raw_contact)

        items_out.append(
            FeedbackDetailResponse(
                id=f.id,
                campaign_id=f.campaign_id,
                campaign_name=f.campaign.name if f.campaign else f"Campaign #{f.campaign_id}",
                message_id=f.message_id,
                audience_member_id=f.audience_member_id,
                recipient_name=recip_name,
                recipient_contact=masked_contact,
                rating=f.rating,
                comment=f.comment,
                sentiment_label=f.sentiment_label,
                sentiment_score=f.sentiment_score,
                language=f.language,
                channel=f.channel or "Web",
                is_resolved=f.is_resolved,
                resolution_notes=f.resolution_notes,
                resolved_at=f.resolved_at,
                created_at=f.created_at,
            )
        )

    return FeedbackListResponse(
        items=items_out,
        total=total,
        positive_count=pos_cnt,
        neutral_count=neu_cnt,
        negative_count=neg_cnt,
        average_rating=round(float(avg_rating), 2),
    )


def get_feedback_detail(db: Session, feedback_id: int) -> FeedbackDetailResponse:
    """Retrieves full detail of a specific feedback record."""
    fb = db.get(Feedback, feedback_id)
    if not fb:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Feedback #{feedback_id} not found.",
        )
    member = fb.audience_member
    recip_name = member.name if member else "Anonymous Citizen"
    raw_contact = (member.email or member.phone or "") if member else ""

    return FeedbackDetailResponse(
        id=fb.id,
        campaign_id=fb.campaign_id,
        campaign_name=fb.campaign.name if fb.campaign else f"Campaign #{fb.campaign_id}",
        message_id=fb.message_id,
        audience_member_id=fb.audience_member_id,
        recipient_name=recip_name,
        recipient_contact=mask_contact(raw_contact),
        rating=fb.rating,
        comment=fb.comment,
        sentiment_label=fb.sentiment_label,
        sentiment_score=fb.sentiment_score,
        language=fb.language,
        channel=fb.channel or "Web",
        is_resolved=fb.is_resolved,
        resolution_notes=fb.resolution_notes,
        resolved_at=fb.resolved_at,
        created_at=fb.created_at,
    )


def resolve_feedback(
    db: Session,
    feedback_id: int,
    notes: Optional[str],
    current_user: User,
) -> FeedbackDetailResponse:
    """Marks feedback as resolved with action resolution notes."""
    fb = db.get(Feedback, feedback_id)
    if not fb:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Feedback #{feedback_id} not found.",
        )

    now_utc = datetime.now(timezone.utc)
    fb.is_resolved = True
    fb.resolution_notes = (notes.strip() if notes else f"Resolved by {current_user.full_name}")
    fb.resolved_at = now_utc
    db.commit()
    db.refresh(fb)

    return get_feedback_detail(db, feedback_id)


async def reply_to_feedback(
    db: Session,
    feedback_id: int,
    reply_text: str,
    channel_override: Optional[str],
    current_user: User,
) -> FeedbackReplyResponse:
    """
    Dispatches a government follow-up reply to a citizen regarding their feedback.
    Strictly verifies affirmative citizen consent and utilizes configured channel adapters.
    """
    fb = db.get(Feedback, feedback_id)
    if not fb:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Feedback #{feedback_id} not found.",
        )

    member = fb.audience_member
    if not member:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot reply: Feedback has no associated recipient identity.",
        )

    # Consent check
    if not member.consent_status:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot reply: Citizen has not granted affirmative communication consent.",
        )

    # Determine target channel
    target_channel = channel_override or member.preferred_channel or fb.channel or "SMS"
    if target_channel == "Web":
        target_channel = "SMS" if member.phone else "Email"

    channel_adapter = get_configured_channel(db, target_channel)

    class _ReplyMsg:
        def __init__(self, text, campaign_name):
            self.rendered_content = text
            self.body = text
            self.subject = f"Response to Feedback: {campaign_name}"
            self.title = self.subject
            self.tracking_id = f"trk_{uuid.uuid4().hex[:16]}"

    msg_obj = _ReplyMsg(reply_text.strip(), fb.campaign.name if fb.campaign else "Government Public Advisory")
    send_res = await channel_adapter.send(message=msg_obj, recipient=member)

    # Log to DeliveryLog
    d_log = DeliveryLog(
        message_id=fb.message_id or 1,
        channel=target_channel,
        status="Sent" if send_res.success else "Failed",
        error_message=send_res.error_message if not send_res.success else None,
        retry_count=0,
    )
    db.add(d_log)

    # Automatically mark feedback as resolved with reply note
    if send_res.success:
        fb.is_resolved = True
        fb.resolution_notes = f"Follow-up reply sent via {target_channel} by {current_user.full_name}: '{reply_text[:60]}...'"
        fb.resolved_at = datetime.now(timezone.utc)

    db.commit()

    dest = member.phone if target_channel in ("SMS", "WhatsApp") else member.email
    return FeedbackReplyResponse(
        success=send_res.success,
        feedback_id=fb.id,
        channel=target_channel,
        recipient=mask_contact(dest),
        detail=f"Reply dispatched successfully via {target_channel}." if send_res.success else f"Reply dispatch failed: {send_res.error_message}",
    )
