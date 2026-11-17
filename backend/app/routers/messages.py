"""FastAPI router for Message Management, Failed Messages Querying, and Retries."""

import logging
from typing import Optional, List
from fastapi import APIRouter, Depends, Query, Path, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.user import User
from app.core.dependencies import require_role
from app.schemas.scheduling import (
    FailedMessagesListResponse,
    MessageRetryResponse,
    RetryBatchResponse,
)
from app.services import retry_service, delivery_tracking_service

logger = logging.getLogger("masscommai.messages_router")

router = APIRouter(prefix="/messages", tags=["Messages & Delivery Tracking"])

MESSAGE_READ_ROLES = ["Admin", "Campaign Manager", "Communication Team"]
MESSAGE_WRITE_ROLES = ["Admin", "Campaign Manager"]


@router.get(
    "/failed",
    response_model=FailedMessagesListResponse,
    summary="List all failed messages across campaigns with retry eligibility",
)
def list_all_failed_messages_endpoint(
    campaign_id: Optional[int] = Query(None, description="Optional filter by campaign ID"),
    channel: Optional[str] = Query(None, description="Optional filter by channel (Email, SMS, WhatsApp, Push)"),
    page: int = Query(1, ge=1, description="Page index (1-based)"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    current_user: User = Depends(require_role(MESSAGE_READ_ROLES)),
    db: Session = Depends(get_db),
) -> FailedMessagesListResponse:
    """Retrieves all failed messages with retry eligibility, masked recipient address, and attempt history."""
    return delivery_tracking_service.list_failed_messages(
        db=db,
        campaign_id=campaign_id,
        channel=channel,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/{id}/retry",
    response_model=MessageRetryResponse,
    summary="Retry an individual failed message (Task 15)",
)
async def retry_message_endpoint(
    id: int = Path(..., ge=1, description="Message primary key ID"),
    force: bool = Query(False, description="Bypass retry interval gap check"),
    current_user: User = Depends(require_role(MESSAGE_WRITE_ROLES)),
    db: Session = Depends(get_db),
) -> MessageRetryResponse:
    """
    Retries an individual failed message:
    1. Validates message is not already Delivered.
    2. Enforces maximum 3 attempts ceiling.
    3. Verifies recipient affirmative consent.
    4. Dispatches and updates status and attempt history.
    """
    return await retry_service.retry_single_message(
        db=db,
        message_id=id,
        current_user=current_user,
        force=force,
    )


@router.post(
    "/retry-failed",
    response_model=RetryBatchResponse,
    summary="Retry all eligible failed messages across campaigns",
)
async def retry_all_failed_endpoint(
    current_user: User = Depends(require_role(MESSAGE_WRITE_ROLES)),
    db: Session = Depends(get_db),
) -> RetryBatchResponse:
    """Retries all eligible failed messages across all campaigns."""
    return await retry_service.retry_failed_messages(
        db=db,
        campaign_id=None,
        current_user=current_user,
        force=True,
    )
