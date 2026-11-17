"""Citizen Feedback and Sentiment Analysis Router."""

from __future__ import annotations
import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query, Path, Request, status
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.db.session import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.communication import Feedback
from app.schemas.engagement import (
    PublicFeedbackInfoResponse,
    PublicFeedbackSubmissionRequest,
    FeedbackResponse,
    FeedbackDetailResponse,
    FeedbackListResponse,
    FeedbackResolveRequest,
    FeedbackReplyRequest,
    FeedbackReplyResponse,
)
from app.services import feedback_service, sentiment_service

logger = logging.getLogger("masscommai.feedback")

router = APIRouter(
    prefix="/feedback",
    tags=["Citizen Feedback & Sentiment"],
)


# -----------------------------------------------------------------------------
# Public Feedback Endpoints (Zero Administrator Authentication Required)
# -----------------------------------------------------------------------------

@router.get(
    "/info/{token}",
    response_model=PublicFeedbackInfoResponse,
    summary="Get public feedback metadata by token (No Auth / Zero PII)",
)
def get_public_feedback_info_endpoint(
    token: str = Path(..., description="Unguessable feedback token or message tracking ID"),
    db: Session = Depends(get_db),
):
    """
    Returns public campaign title, objective, and presentation language for the citizen feedback page.
    Guarantees zero exposure of citizen personal contact information.
    """
    return feedback_service.get_public_feedback_info(db=db, token=token)


@router.post(
    "/submit",
    response_model=FeedbackResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit citizen feedback (No Auth Required)",
)
async def submit_public_feedback_endpoint(
    payload: PublicFeedbackSubmissionRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Receives public star rating and optional multilingual citizen comment.
    Automatically classifies sentiment, generates polarity score, and records a 'participate' engagement event.
    """
    user_agent = request.headers.get("user-agent") if request else None
    return await feedback_service.submit_public_feedback(
        db=db,
        payload=payload,
        user_agent=user_agent,
    )


# -----------------------------------------------------------------------------
# Administrative Feedback Monitoring & Resolution Endpoints
# -----------------------------------------------------------------------------

@router.get(
    "",
    response_model=FeedbackListResponse,
    summary="List feedback records with sentiment, channel, and language filters",
)
def list_feedback_endpoint(
    campaign_id: Optional[int] = Query(None, description="Filter by campaign ID"),
    sentiment: Optional[str] = Query(None, description="Positive, Neutral, Negative"),
    channel: Optional[str] = Query(None, description="Email, SMS, WhatsApp, Web"),
    language: Optional[str] = Query(None, description="Language code e.g. en, hi"),
    is_resolved: Optional[bool] = Query(None, description="Filter by resolution state"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Administrative query endpoint for monitoring citizen feedback across campaigns."""
    return feedback_service.list_feedback(
        db=db,
        campaign_id=campaign_id,
        sentiment=sentiment,
        channel=channel,
        language=language,
        is_resolved=is_resolved,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/topics",
    summary="Identify frequent topics, keywords, questions, and concerns",
)
def get_feedback_topics_endpoint(
    campaign_id: Optional[int] = Query(None, description="Optional campaign filter"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Extracts prominent topics, high-frequency keywords, citizen questions,
    and recurring complaints across collected feedback comments.
    """
    stmt = select(Feedback.comment).where(Feedback.comment != None)
    if campaign_id is not None:
        stmt = stmt.where(Feedback.campaign_id == campaign_id)

    comments = list(db.execute(stmt).scalars().all())
    return sentiment_service.extract_topics_and_keywords(comments)


@router.get(
    "/{feedback_id}",
    response_model=FeedbackDetailResponse,
    summary="Get feedback detail view",
)
def get_feedback_detail_endpoint(
    feedback_id: int = Path(..., description="Feedback ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieves full detail of a specific feedback record."""
    return feedback_service.get_feedback_detail(db=db, feedback_id=feedback_id)


@router.post(
    "/{feedback_id}/resolve",
    response_model=FeedbackDetailResponse,
    summary="Mark feedback as resolved with action notes",
)
def resolve_feedback_endpoint(
    feedback_id: int = Path(..., description="Feedback ID"),
    payload: FeedbackResolveRequest = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Marks negative or critical citizen feedback as administratively resolved."""
    notes = payload.resolution_notes if payload else None
    return feedback_service.resolve_feedback(
        db=db,
        feedback_id=feedback_id,
        notes=notes,
        current_user=current_user,
    )


@router.post(
    "/{feedback_id}/reply",
    response_model=FeedbackReplyResponse,
    summary="Dispatch follow-up reply to feedback via citizen communication channel",
)
async def reply_to_feedback_endpoint(
    feedback_id: int = Path(..., description="Feedback ID"),
    payload: FeedbackReplyRequest = ...,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Sends an official government response to citizen feedback.
    Strictly verifies recipient consent and uses existing channel infrastructure.
    """
    return await feedback_service.reply_to_feedback(
        db=db,
        feedback_id=feedback_id,
        reply_text=payload.reply_text,
        channel_override=payload.channel_override,
        current_user=current_user,
    )
