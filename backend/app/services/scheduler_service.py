"""Campaign Scheduler Service managing one-time, daily, and weekly recurring campaigns with timezone support.

Persists schedule state in PostgreSQL/SQLite and registers jobs with APScheduler (AsyncIOScheduler).
Survives application restarts by reloading active schedules upon startup.
"""

from __future__ import annotations
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.cron import CronTrigger
from apscheduler.jobstores.base import JobLookupError

from app.db.session import SessionLocal
from app.models.user import User
from app.models.campaign import Campaign
from app.models.campaign_schedule import CampaignSchedule
from app.schemas.scheduling import (
    CampaignScheduleCreateRequest,
    CampaignScheduleUpdateRequest,
    CampaignScheduleResponse,
    ScheduledCampaignItem,
    ScheduledCampaignsListResponse,
)
from app.schemas.channel_config import CampaignSendRequest

logger = logging.getLogger("masscommai.scheduler")

# Global singleton AsyncIOScheduler
scheduler = AsyncIOScheduler(timezone=ZoneInfo("UTC"))


def get_timezone_obj(tz_name: str) -> ZoneInfo:
    """Safely resolves an IANA timezone identifier with fallback to UTC."""
    try:
        return ZoneInfo(tz_name.strip())
    except (ZoneInfoNotFoundError, ValueError, AttributeError):
        logger.warning("Unrecognized timezone '%s', defaulting to UTC.", tz_name)
        return ZoneInfo("UTC")


def calculate_next_run_time(
    schedule_type: str,
    scheduled_at: Optional[datetime],
    recurrence_time: Optional[str],
    recurrence_days: Optional[List[str]],
    tz_obj: ZoneInfo,
) -> Optional[datetime]:
    """Calculates the next execution timestamp in UTC."""
    now_utc = datetime.now(timezone.utc)

    if schedule_type == "now":
        return now_utc
    elif schedule_type == "once":
        if not scheduled_at:
            return None
        # Ensure scheduled_at is timezone-aware
        if scheduled_at.tzinfo is None:
            scheduled_at = scheduled_at.replace(tzinfo=timezone.utc)
        return scheduled_at.astimezone(timezone.utc)
    elif schedule_type in ("daily", "weekly"):
        if not recurrence_time:
            return None
        try:
            parts = recurrence_time.strip().split(":")
            hour = int(parts[0])
            minute = int(parts[1])
        except (ValueError, IndexError):
            return None

        # Build cron trigger to compute exact next fire time
        day_str = ",".join(recurrence_days) if (schedule_type == "weekly" and recurrence_days) else "*"
        try:
            trigger = CronTrigger(
                hour=hour,
                minute=minute,
                day_of_week=day_str,
                timezone=tz_obj,
            )
            next_local = trigger.get_next_fire_time(None, now_utc.astimezone(tz_obj))
            return next_local.astimezone(timezone.utc) if next_local else None
        except Exception as exc:
            logger.warning("Error computing next run time for cron: %s", exc)
            return None
    return None


async def execute_scheduled_campaign_job(campaign_id: int):
    """
    Asynchronous runner invoked by APScheduler when a scheduled job triggers.
    Runs in a dedicated database session with concurrency protection.
    """
    logger.info("Executing scheduled campaign job for Campaign #%d...", campaign_id)
    with SessionLocal() as db:
        # Load campaign
        campaign = db.get(Campaign, campaign_id)
        if not campaign:
            logger.error("Scheduled campaign #%d not found in database. Aborting job.", campaign_id)
            return

        # Load schedule record
        stmt = select(CampaignSchedule).where(CampaignSchedule.campaign_id == campaign_id)
        schedule_rec = db.execute(stmt).scalar_one_or_none()
        if not schedule_rec:
            logger.error("Schedule record missing for campaign #%d. Aborting job.", campaign_id)
            return

        if schedule_rec.status != "active":
            logger.info("Schedule for campaign #%d is %s (not active). Skipping execution.", campaign_id, schedule_rec.status)
            return

        # Prevent duplicate execution if campaign is already running
        if campaign.status == "Running":
            logger.warning("Campaign #%d is already in Running state. Skipping duplicate trigger.", campaign_id)
            return

        # Campaign must be in Approved or Scheduled state to execute
        if campaign.status not in ("Approved", "Scheduled"):
            logger.warning(
                "Campaign #%d has status '%s' (must be Approved or Scheduled). Skipping run.",
                campaign_id,
                campaign.status,
            )
            return

        # Prepare send request
        send_req = CampaignSendRequest(
            channels=schedule_rec.channels or (campaign.channels if isinstance(campaign.channels, list) else None),
            fallback_order=schedule_rec.fallback_order or ["WhatsApp", "SMS", "Email"],
            enable_fallback=schedule_rec.enable_fallback,
        )

        now_utc = datetime.now(timezone.utc)
        schedule_rec.last_run_at = now_utc
        schedule_rec.execution_count = (schedule_rec.execution_count or 0) + 1
        db.commit()

        # Execute distribution
        from app.services.campaign_sending_service import send_campaign
        try:
            creator_user = campaign.creator
            summary = await send_campaign(
                db=db,
                campaign_id=campaign_id,
                request=send_req,
                current_user=creator_user,
            )
            logger.info(
                "Scheduled campaign #%d executed successfully. Sent: %d, Delivered: %d, Failed: %d.",
                campaign_id,
                summary.sent_messages,
                summary.delivered_messages,
                summary.failed_messages,
            )

            # Update schedule state after run
            if schedule_rec.schedule_type == "once":
                schedule_rec.status = "completed"
                schedule_rec.next_run_at = None
                campaign.status = "Completed"
            else:
                # Calculate next run time for recurring schedule
                tz_obj = get_timezone_obj(schedule_rec.timezone)
                schedule_rec.next_run_at = calculate_next_run_time(
                    schedule_type=schedule_rec.schedule_type,
                    scheduled_at=schedule_rec.scheduled_at,
                    recurrence_time=schedule_rec.recurrence_time,
                    recurrence_days=schedule_rec.recurrence_days,
                    tz_obj=tz_obj,
                )
                # For recurring campaigns, preserve status as Scheduled for future runs
                campaign.status = "Scheduled"

            db.commit()

        except Exception as exc:
            logger.error("Error executing scheduled campaign #%d: %s", campaign_id, exc)
            campaign.status = "Failed"
            db.commit()


def register_apscheduler_job(schedule_rec: CampaignSchedule) -> Optional[str]:
    """Registers or updates a job in APScheduler based on the persistent schedule record."""
    job_id = f"campaign_job_{schedule_rec.campaign_id}"
    tz_obj = get_timezone_obj(schedule_rec.timezone)

    # Remove existing job if present
    try:
        scheduler.remove_job(job_id)
    except JobLookupError:
        pass

    if schedule_rec.status != "active":
        return None

    if schedule_rec.schedule_type == "once":
        run_dt = schedule_rec.scheduled_at
        if not run_dt:
            return None
        if run_dt.tzinfo is None:
            run_dt = run_dt.replace(tzinfo=timezone.utc)

        # If run time is in the past, execute soon (or immediately)
        now_utc = datetime.now(timezone.utc)
        if run_dt < now_utc:
            run_dt = now_utc + timedelta(seconds=2)

        trigger = DateTrigger(run_date=run_dt, timezone=ZoneInfo("UTC"))
        job = scheduler.add_job(
            execute_scheduled_campaign_job,
            trigger=trigger,
            args=[schedule_rec.campaign_id],
            id=job_id,
            replace_existing=True,
            misfire_grace_time=3600,
        )
        return job.id

    elif schedule_rec.schedule_type in ("daily", "weekly"):
        if not schedule_rec.recurrence_time:
            return None
        parts = schedule_rec.recurrence_time.strip().split(":")
        hour = int(parts[0])
        minute = int(parts[1])

        day_of_week = (
            ",".join(schedule_rec.recurrence_days)
            if (schedule_rec.schedule_type == "weekly" and schedule_rec.recurrence_days)
            else "*"
        )

        trigger = CronTrigger(
            hour=hour,
            minute=minute,
            day_of_week=day_of_week,
            timezone=tz_obj,
        )
        job = scheduler.add_job(
            execute_scheduled_campaign_job,
            trigger=trigger,
            args=[schedule_rec.campaign_id],
            id=job_id,
            replace_existing=True,
            misfire_grace_time=3600,
        )
        return job.id

    return None


async def schedule_campaign(
    db: Session,
    campaign_id: int,
    payload: CampaignScheduleCreateRequest,
    current_user: User,
) -> CampaignScheduleResponse:
    """
    Validates, configures, and schedules an approved campaign.
    Supports send immediately ('now'), future date/time ('once'), and daily/weekly recurrence.
    """
    stmt = select(Campaign).where(Campaign.id == campaign_id)
    campaign = db.execute(stmt).scalar_one_or_none()
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
                detail="Access denied: Cannot schedule campaigns of another organization.",
            )

    # Verification: Only campaigns with review status Approved or already Scheduled can be scheduled
    if campaign.status not in ("Approved", "Scheduled"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Campaign #{campaign_id} ('{campaign.name}') cannot be scheduled. "
                f"Only campaigns with review status 'Approved' are permitted. "
                f"Current status: '{campaign.status}'."
            ),
        )

    tz_obj = get_timezone_obj(payload.timezone)

    # Case A: Send immediately ('now')
    if payload.schedule_type == "now":
        now_utc = datetime.now(timezone.utc)
        # Upsert schedule record
        stmt_sc = select(CampaignSchedule).where(CampaignSchedule.campaign_id == campaign_id)
        sc = db.execute(stmt_sc).scalar_one_or_none()
        if not sc:
            sc = CampaignSchedule(campaign_id=campaign_id, execution_count=0)
            db.add(sc)

        sc.schedule_type = "once"
        sc.scheduled_at = now_utc
        sc.timezone = payload.timezone
        sc.status = "completed"
        sc.last_run_at = now_utc
        sc.next_run_at = None
        sc.channels = payload.channels or (campaign.channels if isinstance(campaign.channels, list) else ["Email", "SMS"])
        sc.fallback_order = payload.fallback_order or ["WhatsApp", "SMS", "Email"]
        sc.enable_fallback = payload.enable_fallback
        sc.execution_count = (sc.execution_count or 0) + 1
        db.commit()
        db.refresh(sc)

        # Dispatch synchronously
        from app.services.campaign_sending_service import send_campaign
        send_req = CampaignSendRequest(
            channels=sc.channels,
            fallback_order=sc.fallback_order,
            enable_fallback=sc.enable_fallback,
        )
        await send_campaign(
            db=db,
            campaign_id=campaign_id,
            request=send_req,
            current_user=current_user,
        )

        db.refresh(sc)
        db.refresh(campaign)

        return _build_schedule_response(sc, campaign.name)

    # Case B: Future ('once') or Recurring ('daily', 'weekly')
    now_utc = datetime.now(timezone.utc)
    target_dt = payload.scheduled_at

    if payload.schedule_type == "once":
        if not target_dt:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Scheduled date and time ('scheduled_at') is required for one-time scheduling.",
            )
        if target_dt.tzinfo is None:
            target_dt = target_dt.replace(tzinfo=timezone.utc)
        if target_dt <= now_utc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Scheduled time must be strictly in the future.",
            )

    # Compute next run at
    next_run = calculate_next_run_time(
        schedule_type=payload.schedule_type,
        scheduled_at=target_dt,
        recurrence_time=payload.recurrence_time,
        recurrence_days=payload.recurrence_days,
        tz_obj=tz_obj,
    )

    # Upsert schedule record
    stmt_sc = select(CampaignSchedule).where(CampaignSchedule.campaign_id == campaign_id)
    sc = db.execute(stmt_sc).scalar_one_or_none()
    if not sc:
        sc = CampaignSchedule(campaign_id=campaign_id, execution_count=0)
        db.add(sc)

    sc.schedule_type = payload.schedule_type
    sc.scheduled_at = target_dt
    sc.recurrence_pattern = payload.schedule_type if payload.schedule_type in ("daily", "weekly") else None
    sc.recurrence_time = payload.recurrence_time
    sc.recurrence_days = payload.recurrence_days or []
    sc.timezone = payload.timezone
    sc.status = "active"
    sc.next_run_at = next_run
    sc.channels = payload.channels or (campaign.channels if isinstance(campaign.channels, list) else ["Email", "SMS"])
    sc.fallback_order = payload.fallback_order or ["WhatsApp", "SMS", "Email"]
    sc.enable_fallback = payload.enable_fallback

    # Transition campaign status to Scheduled
    campaign.status = "Scheduled"
    db.commit()
    db.refresh(sc)

    # Register in APScheduler
    job_id = register_apscheduler_job(sc)
    sc.job_id = job_id
    db.commit()
    db.refresh(sc)

    logger.info("Campaign #%d successfully scheduled (%s, next_run=%s, job_id=%s).", campaign_id, sc.schedule_type, sc.next_run_at, job_id)
    return _build_schedule_response(sc, campaign.name)


def pause_campaign_schedule(
    db: Session,
    campaign_id: int,
    current_user: User,
) -> CampaignScheduleResponse:
    """Pauses an active campaign schedule and pauses its APScheduler job."""
    sc = db.execute(select(CampaignSchedule).where(CampaignSchedule.campaign_id == campaign_id)).scalar_one_or_none()
    if not sc:
        raise HTTPException(status_code=404, detail="Schedule not found for campaign.")

    campaign = db.get(Campaign, campaign_id)
    if sc.status != "active":
        raise HTTPException(status_code=400, detail=f"Cannot pause schedule in '{sc.status}' status.")

    sc.status = "paused"
    if campaign:
        campaign.status = "Paused"

    job_id = f"campaign_job_{campaign_id}"
    try:
        scheduler.pause_job(job_id)
    except JobLookupError:
        pass

    db.commit()
    db.refresh(sc)
    return _build_schedule_response(sc, campaign.name if campaign else "Campaign")


def resume_campaign_schedule(
    db: Session,
    campaign_id: int,
    current_user: User,
) -> CampaignScheduleResponse:
    """Resumes a paused campaign schedule and its APScheduler job."""
    sc = db.execute(select(CampaignSchedule).where(CampaignSchedule.campaign_id == campaign_id)).scalar_one_or_none()
    if not sc:
        raise HTTPException(status_code=404, detail="Schedule not found for campaign.")

    campaign = db.get(Campaign, campaign_id)
    if sc.status != "paused":
        raise HTTPException(status_code=400, detail=f"Cannot resume schedule in '{sc.status}' status (must be paused).")

    sc.status = "active"
    if campaign:
        campaign.status = "Scheduled"

    # Re-compute next run time in case the paused period spanned the previous next_run_at
    tz_obj = get_timezone_obj(sc.timezone)
    sc.next_run_at = calculate_next_run_time(
        schedule_type=sc.schedule_type,
        scheduled_at=sc.scheduled_at,
        recurrence_time=sc.recurrence_time,
        recurrence_days=sc.recurrence_days,
        tz_obj=tz_obj,
    )

    db.commit()
    db.refresh(sc)

    # Register or resume job in APScheduler
    register_apscheduler_job(sc)

    return _build_schedule_response(sc, campaign.name if campaign else "Campaign")


def cancel_campaign_schedule(
    db: Session,
    campaign_id: int,
    current_user: User,
) -> Dict[str, Any]:
    """Cancels and removes a campaign schedule."""
    sc = db.execute(select(CampaignSchedule).where(CampaignSchedule.campaign_id == campaign_id)).scalar_one_or_none()
    if not sc:
        raise HTTPException(status_code=404, detail="Schedule not found for campaign.")

    campaign = db.get(Campaign, campaign_id)
    sc.status = "cancelled"
    sc.next_run_at = None

    if campaign and campaign.status == "Scheduled":
        campaign.status = "Approved"

    job_id = f"campaign_job_{campaign_id}"
    try:
        scheduler.remove_job(job_id)
    except JobLookupError:
        pass

    db.commit()
    return {"status": "ok", "message": f"Schedule for campaign #{campaign_id} cancelled."}


def get_campaign_schedule(
    db: Session,
    campaign_id: int,
) -> CampaignScheduleResponse:
    """Retrieves schedule details for a specific campaign."""
    sc = db.execute(select(CampaignSchedule).where(CampaignSchedule.campaign_id == campaign_id)).scalar_one_or_none()
    if not sc:
        raise HTTPException(status_code=404, detail="No schedule found for this campaign.")
    campaign = db.get(Campaign, campaign_id)
    return _build_schedule_response(sc, campaign.name if campaign else "Campaign")


def list_scheduled_campaigns(
    db: Session,
    status_filter: Optional[str] = None,
) -> ScheduledCampaignsListResponse:
    """Retrieves all scheduled campaigns for calendar and management displays."""
    stmt = (
        select(CampaignSchedule, Campaign)
        .join(Campaign, CampaignSchedule.campaign_id == Campaign.id)
        .order_by(CampaignSchedule.next_run_at.asc().nullslast(), CampaignSchedule.id.desc())
    )
    if status_filter:
        stmt = stmt.where(CampaignSchedule.status == status_filter)

    results = db.execute(stmt).all()
    items: List[ScheduledCampaignItem] = []

    for sc, c in results:
        items.append(
            ScheduledCampaignItem(
                schedule_id=sc.id,
                campaign_id=c.id,
                campaign_name=c.name,
                campaign_status=c.status,
                campaign_type=c.campaign_type,
                priority=c.priority,
                schedule_type=sc.schedule_type,
                scheduled_at=sc.scheduled_at,
                next_run_at=sc.next_run_at,
                last_run_at=sc.last_run_at,
                recurrence_time=sc.recurrence_time,
                recurrence_days=sc.recurrence_days or [],
                timezone=sc.timezone,
                status=sc.status,
                execution_count=sc.execution_count,
                channels=sc.channels or [],
            )
        )

    return ScheduledCampaignsListResponse(total=len(items), items=items)


def initialize_persisted_schedules():
    """
    Invoked during application startup.
    Loads all active schedules from the database and registers them in APScheduler,
    guaranteeing scheduled jobs survive application restarts.
    """
    logger.info("Initializing persisted campaign schedules from database...")
    try:
        with SessionLocal() as db:
            stmt = select(CampaignSchedule).where(CampaignSchedule.status == "active")
            active_schedules = db.execute(stmt).scalars().all()
            reloaded_count = 0
            for sc in active_schedules:
                job_id = register_apscheduler_job(sc)
                if job_id:
                    reloaded_count += 1
            logger.info("Successfully reloaded %d active campaign schedule(s) into APScheduler.", reloaded_count)
    except Exception as exc:
        logger.warning("Could not initialize persisted schedules on startup: %s", exc)


def start_scheduler():
    """Starts the global APScheduler instance if not already running."""
    if not scheduler.running:
        scheduler.start()
        logger.info("APScheduler AsyncIOScheduler started.")
        # Reload persistent schedules
        initialize_persisted_schedules()

        # Register background retry processor (every 60s)
        from app.services.retry_service import process_automatic_retries
        scheduler.add_job(
            process_automatic_retries,
            trigger=CronTrigger(minute="*"),  # every minute
            id="periodic_retry_worker",
            replace_existing=True,
        )

        # Register background automation rules evaluator (every 60s)
        from app.services.automation_service import process_all_automation_rules
        scheduler.add_job(
            process_all_automation_rules,
            trigger=CronTrigger(minute="*"),  # every minute
            id="periodic_automation_rules_worker",
            replace_existing=True,
        )


def shutdown_scheduler():
    """Gracefully terminates APScheduler."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("APScheduler AsyncIOScheduler shut down.")


def _build_schedule_response(sc: CampaignSchedule, campaign_name: str) -> CampaignScheduleResponse:
    return CampaignScheduleResponse(
        id=sc.id,
        campaign_id=sc.campaign_id,
        campaign_name=campaign_name,
        schedule_type=sc.schedule_type,
        scheduled_at=sc.scheduled_at,
        recurrence_pattern=sc.recurrence_pattern,
        recurrence_time=sc.recurrence_time,
        recurrence_days=sc.recurrence_days or [],
        timezone=sc.timezone,
        status=sc.status,
        last_run_at=sc.last_run_at,
        next_run_at=sc.next_run_at,
        job_id=sc.job_id,
        execution_count=sc.execution_count,
        channels=sc.channels or [],
        fallback_order=sc.fallback_order or [],
        enable_fallback=sc.enable_fallback,
        created_at=sc.created_at,
        updated_at=sc.updated_at,
    )
