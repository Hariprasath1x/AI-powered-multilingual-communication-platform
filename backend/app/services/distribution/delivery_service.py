"""Distribution delivery processing, worker orchestration, bounded batch execution, and operational metrics."""

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Tuple, Dict, Any
from sqlalchemy import select, func, distinct, or_
from sqlalchemy.orm import Session, joinedload
from fastapi import HTTPException, status

from app.models.distribution import DistributionJob, DeliveryRecord, DeliveryAttempt
from app.models.audience import AudienceMember
from app.models.content_asset import ContentAsset
from app.models.user import User
from app.models.communication import Message, DeliveryLog
from app.services.distribution.base import (
    JobStatus,
    DeliveryStatus,
    NON_RETRYABLE_ERROR_CODES,
)
from app.services.distribution.consent_validator import revalidate_jit_eligibility
from app.services.channel_constraints import calculate_channel_metrics, WarningSeverity
from app.services.distribution.providers import get_provider
from app.services.distribution.providers.base_provider import DeliveryPayload
from app.services.distribution.job_service import (
    get_distribution_job_by_uuid,
    resolve_campaign_content_assets,
    resolve_recipient_content_variant,
    normalize_language_code,
)

logger = logging.getLogger("masscommai.delivery_service")


def claim_next_queued_job(
    db: Session,
    worker_id: str,
    lease_seconds: int = 300,
) -> Optional[DistributionJob]:
    """
    Atomically claims the next eligible queued job using PostgreSQL row-level locks
    (SELECT ... FOR UPDATE SKIP LOCKED) or transactional claim on SQLite.
    Transitions status to 'processing' and assigns worker lease.
    """
    bind = db.get_bind()
    is_postgres = bool(bind and bind.dialect.name == "postgresql")
    now = datetime.now(timezone.utc)
    lease_expiry = now + timedelta(seconds=lease_seconds)

    stmt = (
        select(DistributionJob)
        .where(DistributionJob.status == JobStatus.QUEUED.value)
        .order_by(DistributionJob.id.asc())
        .limit(1)
    )
    if is_postgres:
        stmt = stmt.with_for_update(of=DistributionJob, skip_locked=True)

    job = db.execute(stmt).unique().scalar_one_or_none()
    if not job:
        return None

    job.status = JobStatus.PROCESSING.value
    job.locked_by = worker_id
    job.locked_at = now
    job.last_heartbeat_at = now
    job.lease_expires_at = lease_expiry
    if not job.started_at:
        job.started_at = now

    db.commit()
    db.refresh(job)

    logger.info(
        "Worker %s successfully claimed Job ID %s (UUID %s). Lease expires at %s.",
        worker_id,
        job.id,
        job.job_id,
        lease_expiry.isoformat(),
    )
    return job


def recover_stale_jobs(
    db: Session,
    lease_seconds: int = 300,
    max_recoveries: int = 3,
) -> List[DistributionJob]:
    """
    Scans for jobs stuck in 'processing' whose worker lease has expired.
    Enforces recovery boundaries:
    - If recovery_count >= max_recoveries: marks job as FAILED.
    - Else: increments recovery_count, resets status to QUEUED, and resets any
      in-progress delivery records to pending/retrying so JIT consent is revalidated.
    """
    now = datetime.now(timezone.utc)
    stale_threshold = now - timedelta(seconds=lease_seconds)
    bind = db.get_bind()
    is_postgres = bool(bind and bind.dialect.name == "postgresql")

    stmt = (
        select(DistributionJob)
        .where(
            DistributionJob.status == JobStatus.PROCESSING.value,
            or_(
                DistributionJob.lease_expires_at < now,
                (DistributionJob.lease_expires_at.is_(None) & (DistributionJob.last_heartbeat_at < stale_threshold)),
                (DistributionJob.lease_expires_at.is_(None) & DistributionJob.last_heartbeat_at.is_(None) & (DistributionJob.started_at < stale_threshold)),
            ),
        )
        .order_by(DistributionJob.id.asc())
    )
    if is_postgres:
        stmt = stmt.with_for_update(of=DistributionJob, skip_locked=True)
    stale_jobs = db.execute(stmt).scalars().all()
    recovered: List[DistributionJob] = []

    for job in stale_jobs:
        if job.recovery_count >= max_recoveries:
            logger.error(
                "Job ID %s exceeded max recoveries (%s/%s). Marking as FAILED.",
                job.id,
                job.recovery_count,
                max_recoveries,
            )
            job.status = JobStatus.FAILED.value
            job.error_summary = f"Job crashed or stalled. Exceeded maximum automated recoveries ({max_recoveries})."
            job.completed_at = now
            job.locked_by = None
            job.lease_expires_at = None
        else:
            job.recovery_count += 1
            prev_worker = job.locked_by or "unknown"
            logger.warning(
                "Recovering stale Job ID %s from worker %s (attempt %s/%s). Re-queueing.",
                job.id,
                prev_worker,
                job.recovery_count,
                max_recoveries,
            )
            job.status = JobStatus.QUEUED.value
            job.locked_by = None
            job.lease_expires_at = None

            # Reset any records left in 'processing' by crashed worker
            orphaned_records = db.execute(
                select(DeliveryRecord).where(
                    DeliveryRecord.job_id == job.id,
                    DeliveryRecord.delivery_status == DeliveryStatus.PROCESSING.value,
                )
            ).scalars().all()
            for r in orphaned_records:
                if r.attempt_count > 0:
                    r.delivery_status = DeliveryStatus.RETRYING.value
                else:
                    r.delivery_status = DeliveryStatus.PENDING.value

        recovered.append(job)

    if recovered:
        db.commit()

    return recovered


def update_worker_heartbeat(
    db: Session,
    job_id: int,
    worker_id: str,
    lease_seconds: int = 300,
) -> bool:
    """Updates last_heartbeat_at and lease_expires_at for active job lease."""
    now = datetime.now(timezone.utc)
    lease_expiry = now + timedelta(seconds=lease_seconds)
    stmt = select(DistributionJob).where(
        DistributionJob.id == job_id,
        DistributionJob.locked_by == worker_id,
        DistributionJob.status == JobStatus.PROCESSING.value,
    )
    job = db.execute(stmt).scalar_one_or_none()
    if job:
        job.last_heartbeat_at = now
        job.lease_expires_at = lease_expiry
        db.commit()
        return True
    return False


async def process_job_batch(
    db: Session,
    job_uuid: str,
    batch_size: int = 50,
    worker_id: Optional[str] = None,
    base_backoff_seconds: int = 60,
    max_backoff_seconds: int = 3600,
    expected_recovery_count: Optional[int] = None,
) -> Tuple[int, bool]:
    """
    Processes a bounded batch of delivery records for a DistributionJob.
    Guarantees:
    1. Bounded memory consumption (loads at most batch_size records).
    2. Atomic claiming of records into 'processing' state.
    3. Full Just-In-Time (JIT) consent and credential revalidation.
    4. Exponential backoff scheduling for retryable failures.
    5. Finalizes job status when all records reach terminal state.
    6. Double-fenced lease protection via locked_by and lease generation (expected_recovery_count).

    Returns:
        (records_processed_in_batch, has_more_records_pending)
    """
    stmt = (
        select(DistributionJob)
        .options(
            joinedload(DistributionJob.campaign),
            joinedload(DistributionJob.creator),
        )
        .where(DistributionJob.job_id == job_uuid)
    )
    job = db.execute(stmt).unique().scalar_one_or_none()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Distribution job with ID '{job_uuid}' not found.",
        )

    if job.status == JobStatus.CANCELLED.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot process a cancelled distribution job.",
        )

    # If job is already in terminal state, return immediately without re-transitioning
    if job.status in (
        JobStatus.COMPLETED.value,
        JobStatus.COMPLETED_WITH_ERRORS.value,
        JobStatus.FAILED.value,
    ):
        return 0, False

    # Worker lease ownership guard: ensure a worker that lost its lease cannot process or overwrite another worker
    if worker_id and job.locked_by and job.locked_by != worker_id:
        logger.warning(
            "Worker %s does not hold active processing lease for Job ID %s (currently locked by %s). Aborting batch.",
            worker_id,
            job.id,
            job.locked_by,
        )
        return 0, False

    # Lease generation token guard: prevent stale workers or identity reuse from executing post-recovery
    if expected_recovery_count is not None and job.recovery_count != expected_recovery_count:
        logger.warning(
            "Worker %s lease generation token expired for Job ID %s (expected %s, actual %s). Aborting batch.",
            worker_id,
            job.id,
            expected_recovery_count,
            job.recovery_count,
        )
        return 0, False

    # Ensure job is marked processing
    if job.status != JobStatus.PROCESSING.value:
        job.status = JobStatus.PROCESSING.value
        if not job.started_at:
            job.started_at = datetime.now(timezone.utc)
        if worker_id:
            job.locked_by = worker_id
            job.locked_at = datetime.now(timezone.utc)
            job.lease_expires_at = datetime.now(timezone.utc) + timedelta(seconds=300)
        db.commit()

    now = datetime.now(timezone.utc)
    bind = db.get_bind()
    is_postgres = bool(bind and bind.dialect.name == "postgresql")

    # Select bounded batch of actionable records (pending or retrying where next_retry_at <= now)
    record_stmt = (
        select(DeliveryRecord)
        .options(joinedload(DeliveryRecord.audience_member))
        .where(
            DeliveryRecord.job_id == job.id,
            DeliveryRecord.delivery_status.in_([DeliveryStatus.PENDING.value, DeliveryStatus.RETRYING.value]),
            or_(
                DeliveryRecord.next_retry_at.is_(None),
                DeliveryRecord.next_retry_at <= now,
            ),
        )
        .order_by(DeliveryRecord.id.asc())
        .limit(batch_size)
    )
    if is_postgres:
        record_stmt = record_stmt.with_for_update(of=DeliveryRecord, skip_locked=True)

    records = db.execute(record_stmt).scalars().all()

    # If no actionable records in this batch
    if not records:
        # Check if any records are still scheduled for future retry
        future_retries = db.scalar(
            select(func.count(DeliveryRecord.id)).where(
                DeliveryRecord.job_id == job.id,
                DeliveryRecord.delivery_status == DeliveryStatus.RETRYING.value,
                DeliveryRecord.next_retry_at > now,
            )
        ) or 0

        pending_or_processing = db.scalar(
            select(func.count(DeliveryRecord.id)).where(
                DeliveryRecord.job_id == job.id,
                DeliveryRecord.delivery_status.in_([DeliveryStatus.PENDING.value, DeliveryStatus.PROCESSING.value]),
            )
        ) or 0

        if future_retries > 0 or pending_or_processing > 0:
            # Still waiting on backoff or concurrent batches
            job.status = JobStatus.QUEUED.value
            db.commit()
            return 0, False

        # Finalize job status
        _finalize_job_status(db, job)
        return 0, False

    # Claim records into 'processing' state atomically
    for rec in records:
        rec.delivery_status = DeliveryStatus.PROCESSING.value
    db.commit()

    provider = get_provider(job.channel)
    root_asset, variants_by_lang = resolve_campaign_content_assets(db, job.campaign, job.channel)

    for rec in records:
        member = rec.audience_member
        now_ts = datetime.now(timezone.utc)

        # Resolve delivery language and fallback metadata
        pref_lang = normalize_language_code(member.preferred_language if member else "en")
        _, selected_asset, resolved_lang, is_fallback = resolve_recipient_content_variant(
            preferred_language=pref_lang,
            approved_variants_by_lang=variants_by_lang,
            root_asset=root_asset,
            fallback_template=job.campaign.template.body if job.campaign.template else "",
        )
        content_asset_id = selected_asset.id if selected_asset else job.content_asset_id

        # 1. JIT Consent & Credential Revalidation
        is_eligible, jit_err_code, jit_err_msg = revalidate_jit_eligibility(
            db, rec.audience_member_id, rec.channel
        )

        if not is_eligible:
            rec.error_code = jit_err_code
            rec.error_message = jit_err_msg
            rec.last_attempt_at = now_ts
            rec.next_retry_at = None

            attempt_meta = {
                "preferred_language": pref_lang,
                "resolved_language": resolved_lang,
                "fallback_to_root": is_fallback,
                "content_asset_id": content_asset_id,
            }

            if jit_err_code in ("CONSENT_WITHDRAWN_POST_JOB", "CONSENT_UNCONFIRMED_POST_JOB", "LACKS_AFFIRMATIVE_CONSENT"):
                rec.delivery_status = DeliveryStatus.SKIPPED_CONSENT.value
                job.skipped_recipients += 1

                attempt = DeliveryAttempt(
                    delivery_record_id=rec.id,
                    attempt_number=rec.attempt_count + 1,
                    provider_name=provider.get_provider_name(),
                    attempt_status="skipped",
                    started_at=now_ts,
                    completed_at=now_ts,
                    error_code=jit_err_code,
                    error_message=jit_err_msg,
                    response_metadata=attempt_meta,
                )
                db.add(attempt)
            else:
                rec.delivery_status = DeliveryStatus.FAILED.value
                job.failed_recipients += 1

                attempt = DeliveryAttempt(
                    delivery_record_id=rec.id,
                    attempt_number=rec.attempt_count + 1,
                    provider_name=provider.get_provider_name(),
                    attempt_status="failure",
                    started_at=now_ts,
                    completed_at=now_ts,
                    error_code=jit_err_code,
                    error_message=jit_err_msg,
                    response_metadata=attempt_meta,
                )
                db.add(attempt)
            continue

        # 2. Phase 1A Invariant E: JIT Content Approval & Quality Readiness Pre-Flight
        asset_to_check = selected_asset or root_asset
        if not asset_to_check and job.content_asset_id:
            asset_to_check = db.get(ContentAsset, job.content_asset_id)

        if asset_to_check is not None:
            from app.services.quality_service import validate_content_dispatch_eligibility
            is_content_ok, content_err_code, content_err_msg = validate_content_dispatch_eligibility(
                db, asset_to_check
            )
            if not is_content_ok:
                logger.error(
                    "Worker pre-flight rejected dispatch for record %s: %s",
                    rec.id,
                    content_err_msg,
                )
                rec.delivery_status = DeliveryStatus.FAILED.value
                rec.error_code = content_err_code or "CONTENT_NOT_ELIGIBLE"
                rec.error_message = content_err_msg
                rec.next_retry_at = None
                rec.last_attempt_at = now_ts
                job.failed_recipients += 1

                attempt_meta = {
                    "preferred_language": pref_lang,
                    "resolved_language": resolved_lang,
                    "fallback_to_root": is_fallback,
                    "content_asset_id": content_asset_id,
                }
                attempt = DeliveryAttempt(
                    delivery_record_id=rec.id,
                    attempt_number=rec.attempt_count + 1,
                    provider_name=provider.get_provider_name(),
                    attempt_status="failure",
                    started_at=now_ts,
                    completed_at=now_ts,
                    error_code=content_err_code or "CONTENT_NOT_ELIGIBLE",
                    error_message=content_err_msg,
                    response_metadata=attempt_meta,
                )
                db.add(attempt)
                continue

        # 3. Dispatch via mock provider
        rec.attempt_count += 1
        rec.last_attempt_at = now_ts

        payload = DeliveryPayload(
            recipient_id=rec.audience_member_id,
            recipient_address=rec.recipient_address,
            recipient_name=member.name if member else f"Recipient #{rec.audience_member_id}",
            channel=rec.channel,
            subject=f"Notice: {job.campaign.name}",
            body=rec.rendered_content,
            metadata={
                "job_id": job.id,
                "job_uuid": job.job_id,
                "attempt": rec.attempt_count,
                "preferred_language": pref_lang,
                "resolved_language": resolved_lang,
                "fallback_to_root": is_fallback,
                "content_asset_id": content_asset_id,
            },
        )

        # Phase D: Pre-dispatch technical hard-limit validation
        payload_metrics = calculate_channel_metrics(
            channel=rec.channel,
            title=payload.subject,
            body=payload.body,
            language=resolved_lang,
            is_template=bool(job.template_id or (selected_asset and getattr(selected_asset, "operation_type", None) == "template")),
        )

        if not payload_metrics.is_within_hard_limit:
            err_msg = "; ".join(w.message for w in payload_metrics.warnings if w.severity == WarningSeverity.CRITICAL.value)
            if not err_msg:
                err_msg = f"Payload exceeds {rec.channel} technical hard limit."

            logger.error("Rejecting dispatch for delivery record %s: %s", rec.id, err_msg)
            rec.delivery_status = DeliveryStatus.FAILED.value
            rec.error_code = "PAYLOAD_EXCEEDS_CHANNEL_HARD_LIMIT"
            rec.error_message = err_msg
            rec.next_retry_at = None
            rec.last_attempt_at = now_ts
            job.failed_recipients += 1

            attempt_meta = {
                "preferred_language": pref_lang,
                "resolved_language": resolved_lang,
                "fallback_to_root": is_fallback,
                "content_asset_id": content_asset_id,
                "channel_metrics": payload_metrics.to_dict(),
                "hard_limit_violation": True,
            }
            attempt = DeliveryAttempt(
                delivery_record_id=rec.id,
                attempt_number=rec.attempt_count,
                provider_name=provider.get_provider_name(),
                attempt_status="failure",
                started_at=now_ts,
                completed_at=now_ts,
                error_code="PAYLOAD_EXCEEDS_CHANNEL_HARD_LIMIT",
                error_message=err_msg,
                response_metadata=attempt_meta,
            )
            db.add(attempt)
            continue

        attempt_start = datetime.now(timezone.utc)
        try:
            result = await provider.send_message(payload)
        except Exception as exc:
            logger.error("Provider execution raised unexpected exception: %s", exc)
            result = None

        attempt_end = datetime.now(timezone.utc)

        # 3. Process dispatch outcome
        if result and result.success:
            rec.delivery_status = DeliveryStatus.DELIVERED.value
            rec.provider_name = result.provider_name
            rec.provider_reference = result.provider_reference
            rec.delivered_at = attempt_end
            rec.error_code = None
            rec.error_message = None
            rec.next_retry_at = None

            job.delivered_recipients += 1
            job.sent_recipients += 1

            attempt_meta = dict(result.response_metadata or {})
            attempt_meta.update({
                "preferred_language": pref_lang,
                "resolved_language": resolved_lang,
                "fallback_to_root": is_fallback,
                "content_asset_id": content_asset_id,
                "channel_metrics": payload_metrics.to_dict(),
            })

            attempt = DeliveryAttempt(
                delivery_record_id=rec.id,
                attempt_number=rec.attempt_count,
                provider_name=result.provider_name,
                attempt_status="success",
                started_at=attempt_start,
                completed_at=attempt_end,
                response_metadata=attempt_meta,
            )
            db.add(attempt)

            # Sync to legacy messages & delivery_logs
            try:
                legacy_msg = Message(
                    campaign_id=job.campaign_id,
                    audience_member_id=rec.audience_member_id,
                    template_id=job.template_id,
                    channel=rec.channel,
                    language=resolved_lang,
                    rendered_content=rec.rendered_content,
                    status="Delivered",
                    sent_at=attempt_end,
                )
                db.add(legacy_msg)
                db.flush()

                legacy_log = DeliveryLog(
                    message_id=legacy_msg.id,
                    channel=rec.channel,
                    status="Delivered",
                    retry_count=rec.attempt_count - 1,
                    timestamp=attempt_end,
                )
                db.add(legacy_log)
            except Exception as sync_exc:
                logger.warning("Legacy message sync warning: %s", sync_exc)

        else:
            err_code = result.error_code if result else "PROVIDER_EXECUTION_FAILURE"
            err_msg = result.error_message if result else "Provider execution threw an unhandled error."
            prov_name = result.provider_name if result else provider.get_provider_name()
            is_retryable = result.is_retryable if result else False

            rec.provider_name = prov_name
            rec.error_code = err_code
            rec.error_message = err_msg

            can_retry = (
                is_retryable
                and (err_code not in NON_RETRYABLE_ERROR_CODES)
                and (rec.attempt_count < rec.max_attempts)
            )

            if can_retry:
                rec.delivery_status = DeliveryStatus.RETRYING.value
                backoff_secs = min(
                    max_backoff_seconds,
                    base_backoff_seconds * (2 ** (rec.attempt_count - 1)),
                )
                rec.next_retry_at = now_ts + timedelta(seconds=backoff_secs)
            else:
                rec.delivery_status = DeliveryStatus.FAILED.value
                rec.next_retry_at = None
                job.failed_recipients += 1

            attempt_meta = dict(result.response_metadata or {}) if result else {}
            attempt_meta.update({
                "preferred_language": pref_lang,
                "resolved_language": resolved_lang,
                "fallback_to_root": is_fallback,
                "content_asset_id": content_asset_id,
            })

            attempt = DeliveryAttempt(
                delivery_record_id=rec.id,
                attempt_number=rec.attempt_count,
                provider_name=prov_name,
                attempt_status="failure",
                started_at=attempt_start,
                completed_at=attempt_end,
                error_code=err_code,
                error_message=err_msg,
                response_metadata=attempt_meta,
            )
            db.add(attempt)

    # Fencing guard: atomically acquire exclusive row lock on PostgreSQL and revalidate lease ownership & generation before persisting batch results
    fencing_stmt = (
        select(DistributionJob.locked_by, DistributionJob.recovery_count)
        .where(DistributionJob.id == job.id)
    )
    if is_postgres:
        fencing_stmt = fencing_stmt.with_for_update()

    current_job_state = db.execute(fencing_stmt).first()
    if current_job_state:
        current_locked_by, current_recovery = current_job_state
        if worker_id and current_locked_by and current_locked_by != worker_id:
            logger.warning(
                "Worker %s lost active lease during batch dispatch for Job ID %s (current owner: %s). Rolling back batch.",
                worker_id,
                job.id,
                current_locked_by,
            )
            db.rollback()
            return 0, False
        if expected_recovery_count is not None and current_recovery != expected_recovery_count:
            logger.warning(
                "Worker %s lease generation expired during batch dispatch for Job ID %s (expected %s, actual %s). Rolling back batch.",
                worker_id,
                job.id,
                expected_recovery_count,
                current_recovery,
            )
            db.rollback()
            return 0, False

    # Refresh worker heartbeat
    now_end = datetime.now(timezone.utc)
    job.last_heartbeat_at = now_end
    job.lease_expires_at = now_end + timedelta(seconds=300)
    db.commit()

    # Check if more records remain to be processed
    remaining_count = db.scalar(
        select(func.count(DeliveryRecord.id)).where(
            DeliveryRecord.job_id == job.id,
            DeliveryRecord.delivery_status.in_([DeliveryStatus.PENDING.value, DeliveryStatus.RETRYING.value]),
        )
    ) or 0

    if remaining_count == 0:
        _finalize_job_status(db, job, worker_id=worker_id, expected_recovery_count=expected_recovery_count)
        return len(records), False

    return len(records), True


def _finalize_job_status(
    db: Session,
    job: DistributionJob,
    worker_id: Optional[str] = None,
    expected_recovery_count: Optional[int] = None,
) -> None:
    """Helper to finalize status, timestamps, and locks when all records of a job are done."""
    bind = db.get_bind()
    is_postgres = bool(bind and bind.dialect.name == "postgresql")

    fencing_stmt = (
        select(DistributionJob.locked_by, DistributionJob.recovery_count)
        .where(DistributionJob.id == job.id)
    )
    if is_postgres:
        fencing_stmt = fencing_stmt.with_for_update()

    current_job_state = db.execute(fencing_stmt).first()
    if current_job_state:
        current_locked_by, current_recovery = current_job_state
        if worker_id and current_locked_by and current_locked_by != worker_id:
            logger.warning(
                "Worker %s lost active lease prior to finalization for Job ID %s (current owner: %s). Aborting finalization.",
                worker_id,
                job.id,
                current_locked_by,
            )
            db.rollback()
            return
        if expected_recovery_count is not None and current_recovery != expected_recovery_count:
            logger.warning(
                "Worker %s lease generation expired prior to finalization for Job ID %s (expected %s, actual %s). Aborting finalization.",
                worker_id,
                job.id,
                expected_recovery_count,
                current_recovery,
            )
            db.rollback()
            return

    all_statuses_stmt = select(DeliveryRecord.delivery_status).where(DeliveryRecord.job_id == job.id)
    all_statuses = db.execute(all_statuses_stmt).scalars().all()

    has_retrying = any(s == DeliveryStatus.RETRYING.value for s in all_statuses)
    has_pending = any(s == DeliveryStatus.PENDING.value for s in all_statuses)
    has_processing = any(s == DeliveryStatus.PROCESSING.value for s in all_statuses)

    if has_retrying or has_pending or has_processing:
        job.status = JobStatus.QUEUED.value
    else:
        if job.delivered_recipients > 0 and (job.failed_recipients > 0 or job.skipped_recipients > 0):
            job.status = JobStatus.COMPLETED_WITH_ERRORS.value
        elif job.failed_recipients == 0 and job.skipped_recipients == 0 and job.delivered_recipients > 0:
            job.status = JobStatus.COMPLETED.value
        elif job.delivered_recipients == 0 and job.failed_recipients > 0:
            job.status = JobStatus.FAILED.value
        elif job.delivered_recipients == 0 and job.skipped_recipients > 0:
            job.status = JobStatus.COMPLETED_WITH_ERRORS.value
        else:
            job.status = JobStatus.COMPLETED.value

        job.completed_at = datetime.now(timezone.utc)
        job.locked_by = None
        job.lease_expires_at = None

    db.commit()
    db.refresh(job)


async def process_distribution_job(
    db: Session,
    job_uuid: str,
    current_user: Optional[User] = None,
) -> DistributionJob:
    """
    Executes mock delivery processing for all pending or retrying records of a DistributionJob.
    Delegates batching iteratively to process_job_batch.
    Maintains 100% backwards compatibility with interactive API endpoints and existing tests.
    """
    stmt = (
        select(DistributionJob)
        .options(
            joinedload(DistributionJob.campaign),
            joinedload(DistributionJob.creator),
        )
        .where(DistributionJob.job_id == job_uuid)
    )
    job = db.execute(stmt).unique().scalar_one_or_none()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Distribution job with ID '{job_uuid}' not found.",
        )

    # Permission check if initiated interactively
    if current_user:
        is_admin = current_user.role and current_user.role.name == "Admin"
        if not is_admin and job.created_by != current_user.id and job.campaign.created_by != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to execute this distribution job.",
            )

    # State validation
    if job.status == JobStatus.CANCELLED.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot process a cancelled distribution job.",
        )

    if job.status == JobStatus.PROCESSING.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Distribution job is already actively processing.",
        )

    # Check actionable records
    actionable_count = db.scalar(
        select(func.count(DeliveryRecord.id)).where(
            DeliveryRecord.job_id == job.id,
            DeliveryRecord.delivery_status.in_([DeliveryStatus.PENDING.value, DeliveryStatus.RETRYING.value]),
        )
    ) or 0

    if actionable_count == 0:
        if job.status in (JobStatus.COMPLETED.value, JobStatus.COMPLETED_WITH_ERRORS.value, JobStatus.FAILED.value):
            return job
        job.status = JobStatus.COMPLETED.value
        job.completed_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(job)
        return job

    # Set processing state
    job.status = JobStatus.PROCESSING.value
    if not job.started_at:
        job.started_at = datetime.now(timezone.utc)
    job.locked_by = f"interactive-user-{current_user.id if current_user else 'system'}"
    job.locked_at = datetime.now(timezone.utc)
    job.lease_expires_at = datetime.now(timezone.utc) + timedelta(seconds=600)
    db.commit()

    # Process all batches until complete
    has_more = True
    while has_more:
        _, has_more = await process_job_batch(
            db=db,
            job_uuid=job_uuid,
            batch_size=50,
            worker_id=job.locked_by,
        )

    db.refresh(job)
    return job


async def retry_failed_deliveries(
    db: Session,
    job_uuid: str,
    current_user: User,
) -> DistributionJob:
    """
    Retries failed records for a DistributionJob that have remaining retry attempts
    and are not non-recoverable permanent errors.
    Never duplicates or re-dispatches records already marked as 'delivered' or 'sent'.
    """
    job = get_distribution_job_by_uuid(db, job_uuid, current_user)

    if job.status == JobStatus.CANCELLED.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot retry deliveries for a cancelled distribution job.",
        )

    if job.status == JobStatus.PROCESSING.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Distribution job is already actively processing. Wait for completion before retrying.",
        )

    # Query failed records with attempts remaining
    failed_stmt = select(DeliveryRecord).where(
        DeliveryRecord.job_id == job.id,
        DeliveryRecord.delivery_status == DeliveryStatus.FAILED.value,
        DeliveryRecord.attempt_count < DeliveryRecord.max_attempts,
    )
    all_failed = db.execute(failed_stmt).scalars().all()

    # Filter out records with non-retryable error codes
    failed_records = [r for r in all_failed if r.error_code not in NON_RETRYABLE_ERROR_CODES]

    if not failed_records:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No eligible failed records available for retry. Records may have exceeded max attempts, permanent non-retryable errors, or already succeeded.",
        )

    # Reset eligible failed records to retrying and clear next_retry_at so they can be processed immediately
    for rec in failed_records:
        rec.delivery_status = DeliveryStatus.RETRYING.value
        rec.next_retry_at = None
        job.failed_recipients = max(0, job.failed_recipients - 1)

    job.status = JobStatus.QUEUED.value
    job.completed_at = None
    db.commit()

    # Trigger processing on the retried records
    return await process_distribution_job(db, job_uuid, current_user)


def get_distribution_metrics(db: Session) -> Dict[str, Any]:
    """
    Gathers operational queue processing metrics and delivery performance aggregates
    using efficient SQL count queries without unbounded record loading.
    """
    now = datetime.now(timezone.utc)

    # Job counts by status
    job_counts_query = select(DistributionJob.status, func.count(DistributionJob.id)).group_by(DistributionJob.status)
    job_counts = dict(db.execute(job_counts_query).all())

    total_jobs = sum(job_counts.values())
    queued_jobs = job_counts.get(JobStatus.QUEUED.value, 0)
    processing_jobs = job_counts.get(JobStatus.PROCESSING.value, 0)
    completed_jobs = job_counts.get(JobStatus.COMPLETED.value, 0)
    completed_with_errors_jobs = job_counts.get(JobStatus.COMPLETED_WITH_ERRORS.value, 0)
    failed_jobs = job_counts.get(JobStatus.FAILED.value, 0)
    cancelled_jobs = job_counts.get(JobStatus.CANCELLED.value, 0)

    # Delivery counts by status
    delivery_counts_query = select(DeliveryRecord.delivery_status, func.count(DeliveryRecord.id)).group_by(DeliveryRecord.delivery_status)
    deliv_counts = dict(db.execute(delivery_counts_query).all())

    total_deliveries = sum(deliv_counts.values())
    pending_deliv = deliv_counts.get(DeliveryStatus.PENDING.value, 0)
    processing_deliv = deliv_counts.get(DeliveryStatus.PROCESSING.value, 0)
    delivered_deliv = deliv_counts.get(DeliveryStatus.DELIVERED.value, 0)
    failed_deliv = deliv_counts.get(DeliveryStatus.FAILED.value, 0)
    skipped_deliv = deliv_counts.get(DeliveryStatus.SKIPPED_CONSENT.value, 0)
    retrying_deliv = deliv_counts.get(DeliveryStatus.RETRYING.value, 0)

    # Stale processing jobs count (expired lease or heartbeat timeout)
    stale_threshold = now - timedelta(seconds=300)
    stale_count_stmt = select(func.count(DistributionJob.id)).where(
        DistributionJob.status == JobStatus.PROCESSING.value,
        or_(
            DistributionJob.lease_expires_at < now,
            (DistributionJob.lease_expires_at.is_(None) & (DistributionJob.last_heartbeat_at < stale_threshold)),
            (DistributionJob.lease_expires_at.is_(None) & DistributionJob.last_heartbeat_at.is_(None) & (DistributionJob.started_at < stale_threshold)),
        ),
    )
    stale_jobs = db.scalar(stale_count_stmt) or 0

    # Active workers count (distinct unexpired worker leases)
    active_worker_query = select(DistributionJob.locked_by, DistributionJob.lease_expires_at).where(
        DistributionJob.status == JobStatus.PROCESSING.value,
        DistributionJob.locked_by.is_not(None),
    )
    active_worker_rows = db.execute(active_worker_query).all()
    active_workers_set = set()
    for w_id, expiry in active_worker_rows:
        if expiry:
            exp_utc = expiry if expiry.tzinfo else expiry.replace(tzinfo=timezone.utc)
            if exp_utc >= now:
                active_workers_set.add(w_id)
    active_workers = len(active_workers_set)

    # Average processing duration for completed jobs
    duration_stmt = select(DistributionJob.started_at, DistributionJob.completed_at).where(
        DistributionJob.status.in_([JobStatus.COMPLETED.value, JobStatus.COMPLETED_WITH_ERRORS.value]),
        DistributionJob.started_at.is_not(None),
        DistributionJob.completed_at.is_not(None),
    ).limit(500)
    duration_rows = db.execute(duration_stmt).all()

    avg_duration = None
    if duration_rows:
        durations = [(end - start).total_seconds() for start, end in duration_rows if end >= start]
        if durations:
            avg_duration = round(sum(durations) / len(durations), 2)

    return {
        "total_jobs": total_jobs,
        "queued_jobs": queued_jobs,
        "processing_jobs": processing_jobs,
        "completed_jobs": completed_jobs,
        "completed_with_errors_jobs": completed_with_errors_jobs,
        "failed_jobs": failed_jobs,
        "cancelled_jobs": cancelled_jobs,
        "total_delivery_records": total_deliveries,
        "pending_deliveries": pending_deliv,
        "processing_deliveries": processing_deliv,
        "delivered_deliveries": delivered_deliv,
        "failed_deliveries": failed_deliv,
        "skipped_consent_deliveries": skipped_deliv,
        "retrying_deliveries": retrying_deliv,
        "stale_processing_jobs": stale_jobs,
        "active_workers_count": active_workers,
        "avg_processing_duration_seconds": avg_duration,
    }
