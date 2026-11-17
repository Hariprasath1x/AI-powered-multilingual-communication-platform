"""Tracked link redirect and link registration router."""

from __future__ import annotations
import logging
from typing import Optional

from fastapi import APIRouter, Depends, Request, Response, status, Path
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.engagement import TrackedLinkCreateRequest, TrackedLinkResponse
from app.services import link_tracking_service

logger = logging.getLogger("masscommai.link_tracking")

router = APIRouter(
    tags=["Link Tracking"],
)


@router.get(
    "/r/{link_id}",
    summary="Tracked short link redirect endpoint",
    description="Validates target destination against open-redirect vulnerabilities, records click engagement event, and redirects.",
    response_class=RedirectResponse,
    status_code=status.HTTP_307_TEMPORARY_REDIRECT,
)
def handle_link_redirect(
    link_id: str = Path(..., description="Unique alphanumeric tracked link ID"),
    request: Request = None,
    db: Session = Depends(get_db),
):
    """Processes tracked link click and performs safe redirection."""
    user_agent = request.headers.get("user-agent") if request else None
    accept_lang = request.headers.get("accept-language") if request else None

    dest_url, event = link_tracking_service.process_link_click(
        db=db,
        link_id=link_id,
        user_agent=user_agent,
        accept_language=accept_lang,
    )
    logger.info("Redirecting tracked link '%s' to '%s' (Device: %s)", link_id, dest_url, event.device_info)
    return RedirectResponse(url=dest_url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)


@router.post(
    "/links/track",
    response_model=TrackedLinkResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register outbound destination link for tracking",
)
def create_tracked_link_endpoint(
    payload: TrackedLinkCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Registers an outbound hyperlink for campaign click tracking and safe attribution."""
    tracked = link_tracking_service.create_tracked_link(
        db=db,
        campaign_id=payload.campaign_id,
        original_url=payload.original_url,
        message_id=payload.message_id,
    )
    return tracked
