"""FastAPI router for Multichannel Distribution Jobs, Pre-dispatch Readiness, and Delivery Tracking."""

import logging
from typing import Optional, List
from fastapi import APIRouter, Depends, Query, Path, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.user import User
from app.core.dependencies import require_role
from app.schemas.distribution import (
    JobCreateRequest,
    ReadinessCheckResponse,
    DistributionJobResponse,
    DeliveryRecordResponse,
    DeliveryAttemptResponse,
    PaginatedJobsResponse,
    PaginatedDeliveriesResponse,
    DistributionMetricsResponse,
)
from app.services.distribution.base import mask_recipient_address
from app.services.distribution import (
    check_campaign_readiness,
    create_distribution_job,
    get_distribution_job_by_uuid,
    list_distribution_jobs,
    list_job_delivery_records,
    cancel_distribution_job,
    process_distribution_job,
    retry_failed_deliveries,
    get_distribution_metrics,
)

logger = logging.getLogger("masscommai.distribution_router")

router = APIRouter(prefix="/distribution", tags=["Multichannel Distribution"])

DISTRIBUTION_READ_ROLES = ["Admin", "Campaign Manager", "Communication Team"]
DISTRIBUTION_WRITE_ROLES = ["Admin", "Campaign Manager"]


def _build_job_response(job) -> DistributionJobResponse:
    """Helper to convert DistributionJob model to schema with creator and campaign names."""
    creator_name = job.creator.full_name if job.creator else None
    campaign_name = job.campaign.name if job.campaign else None
    return DistributionJobResponse(
        id=job.id,
        job_id=job.job_id,
        campaign_id=job.campaign_id,
        campaign_name=campaign_name,
        content_asset_id=job.content_asset_id,
        template_id=job.template_id,
        channel=job.channel,
        status=job.status,
        total_recipients=job.total_recipients,
        eligible_recipients=job.eligible_recipients,
        queued_recipients=job.queued_recipients,
        sent_recipients=job.sent_recipients,
        delivered_recipients=job.delivered_recipients,
        failed_recipients=job.failed_recipients,
        skipped_recipients=job.skipped_recipients,
        error_summary=job.error_summary,
        started_at=job.started_at,
        completed_at=job.completed_at,
        locked_by=getattr(job, "locked_by", None),
        lease_expires_at=getattr(job, "lease_expires_at", None),
        recovery_count=getattr(job, "recovery_count", 0),
        created_by=job.created_by,
        creator_name=creator_name,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


def _build_record_response(rec) -> DeliveryRecordResponse:
    """Helper to convert DeliveryRecord model to schema."""
    recipient_name = rec.audience_member.name if rec.audience_member else None
    masked_addr = mask_recipient_address(rec.recipient_address, rec.channel)
    attempts = [
        DeliveryAttemptResponse(
            id=a.id,
            attempt_number=a.attempt_number,
            provider_name=a.provider_name,
            attempt_status=a.attempt_status,
            started_at=a.started_at,
            completed_at=a.completed_at,
            error_code=a.error_code,
            error_message=a.error_message,
            response_metadata=a.response_metadata,
        )
        for a in (rec.attempts or [])
    ]
    return DeliveryRecordResponse(
        id=rec.id,
        delivery_id=rec.delivery_id,
        job_id=rec.job_id,
        audience_member_id=rec.audience_member_id,
        recipient_name=recipient_name,
        channel=rec.channel,
        masked_recipient_address=masked_addr,
        rendered_content=rec.rendered_content,
        delivery_status=rec.delivery_status,
        provider_name=rec.provider_name,
        provider_reference=rec.provider_reference,
        attempt_count=rec.attempt_count,
        max_attempts=rec.max_attempts,
        last_attempt_at=rec.last_attempt_at,
        delivered_at=rec.delivered_at,
        error_code=rec.error_code,
        error_message=rec.error_message,
        created_at=rec.created_at,
        updated_at=rec.updated_at,
        attempts=attempts,
    )


@router.get(
    "/readiness/{campaign_id}",
    response_model=ReadinessCheckResponse,
    summary="Validate campaign distribution readiness for target channel",
)
def evaluate_readiness(
    campaign_id: int = Path(..., description="Campaign ID to assess"),
    channel: str = Query("Email", description="Target channel: Email, SMS, WhatsApp, Voice, Web"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(DISTRIBUTION_READ_ROLES)),
):
    """
    Evaluates whether a campaign is ready for distribution across a specified channel:
    validates lifecycle status ('Approved'), channel support, editorial review clearance,
    attached segments, and affirmative consent counts.
    """
    allowed_channels = {"Email", "SMS", "WhatsApp", "Voice", "Web"}
    if channel not in allowed_channels:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid channel '{channel}'. Allowed: {', '.join(sorted(allowed_channels))}",
        )

    result = check_campaign_readiness(db, campaign_id, channel)
    return ReadinessCheckResponse(
        is_ready=result.is_ready,
        campaign_id=result.campaign_id,
        campaign_status=result.campaign_status,
        campaign_status_valid=result.campaign_status_valid,
        channel=result.channel,
        channel_supported=result.channel_supported,
        has_template_or_content=result.has_template_or_content,
        content_approved=result.content_approved,
        content_is_outdated=result.content_is_outdated,
        total_target_audience=result.total_target_audience,
        confirmed_consent_audience=result.confirmed_consent_audience,
        eligible_recipients_count=result.eligible_recipients_count,
        blocking_reasons=result.blocking_reasons,
        warnings=result.warnings,
        valid_recipients_count=result.valid_recipients_count,
        warning_recipients_count=result.warning_recipients_count,
        blocked_recipients_count=result.blocked_recipients_count,
        total_estimated_segments=result.total_estimated_segments,
        max_segments_per_recipient=result.max_segments_per_recipient,
        estimated_duration_seconds=result.estimated_duration_seconds,
        channel_metrics=result.channel_metrics,
        language_breakdown=result.language_breakdown,
    )


@router.post(
    "/jobs",
    response_model=DistributionJobResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a distribution job for an approved campaign",
)
def create_job(
    payload: JobCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(DISTRIBUTION_WRITE_ROLES)),
):
    """
    Stages a batch distribution job for an approved campaign and target channel.
    Resolves unique recipients, verifies consent, personalizes content, and stages delivery records.
    """
    job = create_distribution_job(
        db=db,
        campaign_id=payload.campaign_id,
        channel=payload.channel,
        current_user=current_user,
    )
    return _build_job_response(job)


@router.get(
    "/jobs",
    response_model=PaginatedJobsResponse,
    summary="List distribution jobs with filtering and pagination",
)
def list_jobs(
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    campaign_id: Optional[int] = Query(None),
    channel: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(DISTRIBUTION_READ_ROLES)),
):
    """Retrieves paginated distribution jobs with ownership boundaries."""
    jobs, total = list_distribution_jobs(
        db=db,
        page=page,
        size=size,
        campaign_id=campaign_id,
        channel=channel,
        status_filter=status_filter,
        current_user=current_user,
    )
    items = [_build_job_response(j) for j in jobs]
    pages = (total + size - 1) // size if total > 0 else 1
    return PaginatedJobsResponse(
        items=items,
        total=total,
        page=page,
        size=size,
        pages=pages,
    )


@router.get(
    "/jobs/{job_id}",
    response_model=DistributionJobResponse,
    summary="Retrieve distribution job details by UUID",
)
def get_job(
    job_id: str = Path(..., description="Public job UUID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(DISTRIBUTION_READ_ROLES)),
):
    """Fetches details, execution timestamps, and aggregate metrics of a distribution job."""
    job = get_distribution_job_by_uuid(db, job_id, current_user)
    return _build_job_response(job)


@router.get(
    "/jobs/{job_id}/deliveries",
    response_model=PaginatedDeliveriesResponse,
    summary="Retrieve recipient delivery outcomes for a distribution job",
)
def get_job_deliveries(
    job_id: str = Path(..., description="Public job UUID"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    delivery_status: Optional[str] = Query(None, alias="status"),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(DISTRIBUTION_READ_ROLES)),
):
    """Retrieves recipient-level delivery logs, attempt histories, and failure explanations."""
    records, total = list_job_delivery_records(
        db=db,
        job_uuid=job_id,
        page=page,
        size=size,
        delivery_status=delivery_status,
        search=search,
        current_user=current_user,
    )
    items = [_build_record_response(r) for r in records]
    pages = (total + size - 1) // size if total > 0 else 1
    return PaginatedDeliveriesResponse(
        items=items,
        total=total,
        page=page,
        size=size,
        pages=pages,
    )


@router.post(
    "/jobs/{job_id}/process",
    response_model=DistributionJobResponse,
    summary="Trigger mock delivery processing for pending/retrying records",
)
async def process_job(
    job_id: str = Path(..., description="Public job UUID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(DISTRIBUTION_WRITE_ROLES)),
):
    """
    Executes mock delivery processing. Evaluates JIT consent, passes records through
    channel mock provider adapters, records granular attempt logs, and finalizes counters.
    """
    job = await process_distribution_job(db, job_id, current_user)
    return _build_job_response(job)


@router.post(
    "/jobs/{job_id}/retry",
    response_model=DistributionJobResponse,
    summary="Retry eligible failed records for a distribution job",
)
async def retry_job(
    job_id: str = Path(..., description="Public job UUID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(DISTRIBUTION_WRITE_ROLES)),
):
    """
    Retries failed records that have remaining attempts without duplicating delivered records.
    """
    job = await retry_failed_deliveries(db, job_id, current_user)
    return _build_job_response(job)


@router.post(
    "/jobs/{job_id}/cancel",
    response_model=DistributionJobResponse,
    summary="Cancel a pending or queued distribution job",
)
def cancel_job(
    job_id: str = Path(..., description="Public job UUID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(DISTRIBUTION_WRITE_ROLES)),
):
    """Cancels a pending or queued distribution job and all its pending records."""
    job = cancel_distribution_job(db, job_id, current_user)
    return _build_job_response(job)


@router.get(
    "/metrics",
    response_model=DistributionMetricsResponse,
    summary="Retrieve operational queue processing metrics and delivery aggregates",
)
def get_metrics(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(DISTRIBUTION_READ_ROLES)),
):
    """
    Exposes system-level queue processing health, active worker leases,
    stale jobs, aggregate delivery states, and average processing latency.
    Requires Admin, Campaign Manager, or Communication Team authentication.
    """
    return get_distribution_metrics(db)


