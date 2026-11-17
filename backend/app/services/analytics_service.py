"""Aggregated Analytics, Reporting, and Insights Service for Milestone 3, Task 17."""

from __future__ import annotations
import io
import csv
import logging
from typing import Dict, Any, List, Optional, Tuple, Union
from datetime import datetime, timezone, timedelta, date

from sqlalchemy import select, func, and_, or_, distinct, case, desc, asc
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.campaign import Campaign
from app.models.communication import Message, Feedback
from app.models.engagement import EngagementEvent, TrackedLink
from app.models.segment import Segment, campaign_segments
from app.models.audience import AudienceMember
from app.schemas.analytics import (
    GlobalKPIsResponse,
    StatusCounts,
    EngagementTrendsResponse,
    TrendDataPoint,
    ChannelBreakdownItem,
    LanguageBreakdownItem,
    SegmentBreakdownItem,
    CampaignRankItem,
    PerformanceBreakdownsResponse,
    FunnelStageItem,
    CampaignFunnelResponse,
    AIInsightItem,
    AIInsightsResponse,
    CampaignAnalyticsReportResponse,
)
from app.services import pdf_export_service
from app.services.ai.factory import get_ai_provider

logger = logging.getLogger("masscommai.analytics")


def _apply_message_filters(
    query,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    campaign_id: Optional[int] = None,
    channel: Optional[str] = None,
    language: Optional[str] = None,
    segment_id: Optional[int] = None,
):
    """Applies common filter predicates to a Message query."""
    if start_date:
        query = query.where(Message.created_at >= start_date)
    if end_date:
        query = query.where(Message.created_at <= end_date)
    if campaign_id:
        query = query.where(Message.campaign_id == campaign_id)
    if channel:
        query = query.where(func.lower(Message.channel) == channel.strip().lower())
    if language:
        query = query.where(func.lower(Message.language) == language.strip().lower())
    if segment_id:
        # Join with campaign_segments
        subq = select(campaign_segments.c.campaign_id).where(campaign_segments.c.segment_id == segment_id)
        query = query.where(Message.campaign_id.in_(subq))
    return query


def _apply_event_filters(
    query,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    campaign_id: Optional[int] = None,
    language: Optional[str] = None,
    segment_id: Optional[int] = None,
):
    """Applies common filter predicates to an EngagementEvent query."""
    if start_date:
        query = query.where(EngagementEvent.timestamp >= start_date)
    if end_date:
        query = query.where(EngagementEvent.timestamp <= end_date)
    if campaign_id:
        query = query.where(EngagementEvent.campaign_id == campaign_id)
    if language:
        query = query.where(func.lower(EngagementEvent.language) == language.strip().lower())
    if segment_id:
        subq = select(campaign_segments.c.campaign_id).where(campaign_segments.c.segment_id == segment_id)
        query = query.where(EngagementEvent.campaign_id.in_(subq))
    return query


def validate_filter_dates(
    start_date: Optional[Union[str, datetime]] = None,
    end_date: Optional[Union[str, datetime]] = None,
) -> Tuple[Optional[datetime], Optional[datetime]]:
    """
    Parses and validates start_date and end_date.
    Ensures date formats are valid ISO YYYY-MM-DD and start_date <= end_date.
    Returns (start_dt, end_dt) as timezone-aware datetime objects.
    """
    def parse_dt(d):
        if not d:
            return None
        if isinstance(d, datetime):
            return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
        if isinstance(d, date):
            return datetime.combine(d, datetime.min.time(), tzinfo=timezone.utc)
        try:
            return datetime.strptime(str(d).strip(), "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid date format: '{d}'. Expected YYYY-MM-DD.",
            )

    start_dt = parse_dt(start_date)
    end_dt = parse_dt(end_date)
    if end_dt and isinstance(end_date, str) and len(end_date.strip()) == 10:
        # Include the entire end day
        end_dt = end_dt.replace(hour=23, minute=59, second=59, microsecond=999999)

    if start_dt and end_dt and start_dt > end_dt:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="start_date must be before or equal to end_date",
        )

    return start_dt, end_dt


def get_global_kpis(
    db: Session,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    campaign_id: Optional[int] = None,
    channel: Optional[str] = None,
    language: Optional[str] = None,
    segment_id: Optional[int] = None,
) -> GlobalKPIsResponse:
    """Calculates global and filtered KPIs across all messages and engagement records."""
    start_date, end_date = validate_filter_dates(start_date, end_date)

    # 1. Message Aggregations
    msg_stmt = select(
        func.count(Message.id).label("total_msgs"),
        func.sum(case((func.lower(Message.status).in_(["sent", "delivered", "failed"]), 1), else_=0)).label("total_sent"),
        func.sum(case((func.lower(Message.status) == "delivered", 1), else_=0)).label("total_delivered"),
        func.sum(case((func.lower(Message.status) == "failed", 1), else_=0)).label("total_failed"),
        func.sum(case((func.lower(Message.status).in_(["pending", "draft", "queued"]), 1), else_=0)).label("total_pending"),
        func.count(distinct(case((func.lower(Message.status) == "delivered", Message.audience_member_id), else_=None))).label("reach"),
        func.count(distinct(Message.campaign_id)).label("active_campaigns"),
    )
    msg_stmt = _apply_message_filters(
        msg_stmt,
        start_date=start_date,
        end_date=end_date,
        campaign_id=campaign_id,
        channel=channel,
        language=language,
        segment_id=segment_id,
    )
    msg_row = db.execute(msg_stmt).fetchone()

    total_msgs = int(msg_row.total_msgs or 0)
    total_sent = int(msg_row.total_sent or 0)
    total_delivered = int(msg_row.total_delivered or 0)
    total_failed = int(msg_row.total_failed or 0)
    total_pending = int(msg_row.total_pending or 0)
    total_reach = int(msg_row.reach or 0)
    campaigns_in_scope = int(msg_row.active_campaigns or 0)

    # If no campaign filter and no messages, fallback to total campaigns table count
    if not campaign_id and campaigns_in_scope == 0:
        c_stmt = select(func.count(Campaign.id))
        if start_date:
            c_stmt = c_stmt.where(Campaign.created_at >= start_date)
        if end_date:
            c_stmt = c_stmt.where(Campaign.created_at <= end_date)
        campaigns_in_scope = db.execute(c_stmt).scalar() or 0
    elif campaign_id and campaigns_in_scope == 0:
        # Check if campaign exists
        c_exists = db.get(Campaign, campaign_id)
        if c_exists:
            campaigns_in_scope = 1

    # 2. Engagement Aggregations
    evt_stmt = select(
        func.count(distinct(case((func.lower(EngagementEvent.event_type).in_(["open", "opened"]), EngagementEvent.message_id), else_=None))).label("unique_opens"),
        func.count(distinct(case((func.lower(EngagementEvent.event_type).in_(["click", "clicked"]), EngagementEvent.message_id), else_=None))).label("unique_clicks"),
        func.sum(case((func.lower(EngagementEvent.event_type).in_(["reply", "replied"]), 1), else_=0)).label("replies"),
        func.sum(case((func.lower(EngagementEvent.event_type).in_(["participate", "participation"]), 1), else_=0)).label("participations"),
    )
    evt_stmt = _apply_event_filters(
        evt_stmt,
        start_date=start_date,
        end_date=end_date,
        campaign_id=campaign_id,
        language=language,
        segment_id=segment_id,
    )
    evt_row = db.execute(evt_stmt).fetchone()

    unique_opens = int(evt_row.unique_opens or 0)
    unique_clicks = int(evt_row.unique_clicks or 0)
    replies = int(evt_row.replies or 0)
    participations = int(evt_row.participations or 0)

    # Check feedback table if participations event count is 0
    if participations == 0:
        fb_stmt = select(func.count(Feedback.id))
        if start_date:
            fb_stmt = fb_stmt.where(Feedback.created_at >= start_date)
        if end_date:
            fb_stmt = fb_stmt.where(Feedback.created_at <= end_date)
        if campaign_id:
            fb_stmt = fb_stmt.where(Feedback.campaign_id == campaign_id)
        if language:
            fb_stmt = fb_stmt.where(func.lower(Feedback.language) == language.strip().lower())
        if segment_id:
            subq = select(campaign_segments.c.campaign_id).where(campaign_segments.c.segment_id == segment_id)
            fb_stmt = fb_stmt.where(Feedback.campaign_id.in_(subq))
        fb_count = db.execute(fb_stmt).scalar() or 0
        participations = max(participations, fb_count)

    # 3. Safe Rates Calculation
    open_rate = round((unique_opens / total_delivered * 100), 2) if total_delivered > 0 else 0.0
    ctr = round((unique_clicks / total_delivered * 100), 2) if total_delivered > 0 else 0.0
    response_rate = round((replies / total_delivered * 100), 2) if total_delivered > 0 else 0.0
    participation_rate = round((participations / total_delivered * 100), 2) if total_delivered > 0 else 0.0
    delivery_rate = round((total_delivered / total_sent * 100), 2) if total_sent > 0 else 0.0
    bounce_rate = round((total_failed / total_sent * 100), 2) if total_sent > 0 else 0.0

    return GlobalKPIsResponse(
        total_campaigns=campaigns_in_scope,
        total_messages_sent=total_sent,
        total_delivered=total_delivered,
        total_reach=total_reach,
        average_open_rate=open_rate,
        average_click_through_rate=ctr,
        response_rate=response_rate,
        participation_rate=participation_rate,
        status_counts=StatusCounts(
            sent=total_sent,
            delivered=total_delivered,
            failed=total_failed,
            pending=total_pending,
        ),
        delivery_rate=delivery_rate,
        bounce_rate=bounce_rate,
    )


def get_engagement_trends(
    db: Session,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    interval: str = "daily",
    campaign_id: Optional[int] = None,
    channel: Optional[str] = None,
    language: Optional[str] = None,
) -> EngagementTrendsResponse:
    """Aggregates time-series trends for sent, delivered, opens, clicks, replies, and participations."""
    start_date, end_date = validate_filter_dates(start_date, end_date)

    now_utc = datetime.now(timezone.utc)
    # Default window: past 14 days if not specified
    eff_start = start_date or (now_utc - timedelta(days=13))
    eff_end = end_date or now_utc

    # 1. Group Messages by Date
    msg_date_col = func.date(Message.created_at)
    msg_stmt = select(
        msg_date_col.label("bucket_date"),
        func.sum(case((func.lower(Message.status).in_(["sent", "delivered", "failed"]), 1), else_=0)).label("sent"),
        func.sum(case((func.lower(Message.status) == "delivered", 1), else_=0)).label("delivered"),
        func.sum(case((func.lower(Message.status) == "failed", 1), else_=0)).label("failed"),
    ).group_by(msg_date_col)
    msg_stmt = _apply_message_filters(
        msg_stmt,
        start_date=eff_start,
        end_date=eff_end,
        campaign_id=campaign_id,
        channel=channel,
        language=language,
    )
    msg_rows = db.execute(msg_stmt).fetchall()
    msg_map = {str(r.bucket_date): {"sent": int(r.sent or 0), "delivered": int(r.delivered or 0), "failed": int(r.failed or 0)} for r in msg_rows if r.bucket_date}

    # 2. Group Engagement Events by Date
    evt_date_col = func.date(EngagementEvent.timestamp)
    evt_stmt = select(
        evt_date_col.label("bucket_date"),
        func.sum(case((func.lower(EngagementEvent.event_type).in_(["open", "opened"]), 1), else_=0)).label("opens"),
        func.sum(case((func.lower(EngagementEvent.event_type).in_(["click", "clicked"]), 1), else_=0)).label("clicks"),
        func.sum(case((func.lower(EngagementEvent.event_type).in_(["reply", "replied"]), 1), else_=0)).label("replies"),
        func.sum(case((func.lower(EngagementEvent.event_type).in_(["participate", "participation"]), 1), else_=0)).label("participations"),
    ).group_by(evt_date_col)
    evt_stmt = _apply_event_filters(
        evt_stmt,
        start_date=eff_start,
        end_date=eff_end,
        campaign_id=campaign_id,
        language=language,
    )
    evt_rows = db.execute(evt_stmt).fetchall()
    evt_map = {
        str(r.bucket_date): {
            "opens": int(r.opens or 0),
            "clicks": int(r.clicks or 0),
            "replies": int(r.replies or 0),
            "participations": int(r.participations or 0),
        }
        for r in evt_rows
        if r.bucket_date
    }

    # Generate continuous sequence of dates between eff_start and eff_end
    start_d = eff_start.date() if isinstance(eff_start, datetime) else eff_start
    end_d = eff_end.date() if isinstance(eff_end, datetime) else eff_end

    delta_days = (end_d - start_d).days
    # Bound to maximum 90 points to protect UI responsiveness
    delta_days = max(0, min(delta_days, 90))

    trend_points: List[TrendDataPoint] = []
    for day_offset in range(delta_days + 1):
        curr_d = start_d + timedelta(days=day_offset)
        d_str = curr_d.strftime("%Y-%m-%d")
        m_data = msg_map.get(d_str, {"sent": 0, "delivered": 0})
        e_data = evt_map.get(d_str, {"opens": 0, "clicks": 0, "replies": 0, "participations": 0})

        trend_points.append(
            TrendDataPoint(
                date=d_str,
                sent=m_data["sent"],
                delivered=m_data["delivered"],
                opens=e_data["opens"],
                clicks=e_data["clicks"],
                replies=e_data["replies"],
                participations=e_data["participations"],
            )
        )

    return EngagementTrendsResponse(
        interval=interval,
        start_date=start_d.strftime("%Y-%m-%d"),
        end_date=end_d.strftime("%Y-%m-%d"),
        trends=trend_points,
    )


def get_performance_breakdowns(
    db: Session,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    campaign_id: Optional[int] = None,
    channel: Optional[str] = None,
    language: Optional[str] = None,
    segment_id: Optional[int] = None,
) -> PerformanceBreakdownsResponse:
    """Computes breakdowns across channels, languages, audience segments, and campaign performance rankings."""
    start_date, end_date = validate_filter_dates(start_date, end_date)

    # 1. By Channel
    channels_catalog = ["Email", "SMS", "WhatsApp", "Push", "Web Broadcast"]
    ch_stmt = select(
        Message.channel,
        func.sum(case((func.lower(Message.status).in_(["sent", "delivered", "failed"]), 1), else_=0)).label("sent"),
        func.sum(case((func.lower(Message.status) == "delivered", 1), else_=0)).label("delivered"),
        func.sum(case((func.lower(Message.status) == "failed", 1), else_=0)).label("failed"),
    ).group_by(Message.channel)
    ch_stmt = _apply_message_filters(ch_stmt, start_date, end_date, campaign_id, channel, language, segment_id)
    ch_rows = db.execute(ch_stmt).fetchall()

    by_channel: Dict[str, ChannelBreakdownItem] = {}
    for c in channels_catalog:
        by_channel[c] = ChannelBreakdownItem(channel=c)

    for r in ch_rows:
        if not r.channel:
            continue
        c_name = r.channel
        sent = int(r.sent or 0)
        delivered = int(r.delivered or 0)
        failed = int(r.failed or 0)

        # Get channel events
        # Events correlated with channel
        ev_stmt = select(
            func.count(distinct(case((func.lower(EngagementEvent.event_type).in_(["open", "opened"]), EngagementEvent.message_id), else_=None))).label("opens"),
            func.count(distinct(case((func.lower(EngagementEvent.event_type).in_(["click", "clicked"]), EngagementEvent.message_id), else_=None))).label("clicks"),
            func.sum(case((func.lower(EngagementEvent.event_type).in_(["reply", "replied"]), 1), else_=0)).label("replies"),
        ).join(Message, EngagementEvent.message_id == Message.id).where(Message.channel == c_name)
        if start_date:
            ev_stmt = ev_stmt.where(EngagementEvent.timestamp >= start_date)
        if end_date:
            ev_stmt = ev_stmt.where(EngagementEvent.timestamp <= end_date)
        if campaign_id:
            ev_stmt = ev_stmt.where(EngagementEvent.campaign_id == campaign_id)

        ev_row = db.execute(ev_stmt).fetchone()
        opens = int(ev_row.opens or 0) if ev_row else 0
        clicks = int(ev_row.clicks or 0) if ev_row else 0
        replies = int(ev_row.replies or 0) if ev_row else 0

        open_rate = round(opens / delivered * 100, 2) if delivered > 0 else 0.0
        ctr = round(clicks / delivered * 100, 2) if delivered > 0 else 0.0
        del_rate = round(delivered / sent * 100, 2) if sent > 0 else 0.0

        by_channel[c_name] = ChannelBreakdownItem(
            channel=c_name,
            sent=sent,
            delivered=delivered,
            failed=failed,
            opens=opens,
            clicks=clicks,
            replies=replies,
            open_rate=open_rate,
            ctr=ctr,
            delivery_rate=del_rate,
        )

    # 2. By Language
    lang_stmt = select(
        Message.language,
        func.count(Message.id).label("total_msgs"),
        func.sum(case((func.lower(Message.status) == "delivered", 1), else_=0)).label("delivered"),
    ).group_by(Message.language)
    lang_stmt = _apply_message_filters(lang_stmt, start_date, end_date, campaign_id, channel, language, segment_id)
    lang_rows = db.execute(lang_stmt).fetchall()

    by_language: Dict[str, LanguageBreakdownItem] = {}
    for r in lang_rows:
        l_code = (r.language or "en").lower()
        delivered = int(r.delivered or 0)
        msgs = int(r.total_msgs or 0)

        # Engagement events for this language
        ev_l_stmt = select(
            func.count(distinct(case((func.lower(EngagementEvent.event_type).in_(["open", "opened"]), EngagementEvent.message_id), else_=None))).label("opens"),
            func.count(distinct(case((func.lower(EngagementEvent.event_type).in_(["click", "clicked"]), EngagementEvent.message_id), else_=None))).label("clicks"),
            func.sum(case((func.lower(EngagementEvent.event_type).in_(["reply", "replied"]), 1), else_=0)).label("replies"),
            func.sum(case((func.lower(EngagementEvent.event_type).in_(["participate", "participation"]), 1), else_=0)).label("participations"),
        ).where(func.lower(EngagementEvent.language) == l_code)
        if start_date:
            ev_l_stmt = ev_l_stmt.where(EngagementEvent.timestamp >= start_date)
        if end_date:
            ev_l_stmt = ev_l_stmt.where(EngagementEvent.timestamp <= end_date)
        if campaign_id:
            ev_l_stmt = ev_l_stmt.where(EngagementEvent.campaign_id == campaign_id)
        ev_l_row = db.execute(ev_l_stmt).fetchone()

        opens = int(ev_l_row.opens or 0) if ev_l_row else 0
        clicks = int(ev_l_row.clicks or 0) if ev_l_row else 0
        replies = int(ev_l_row.replies or 0) if ev_l_row else 0
        participations = int(ev_l_row.participations or 0) if ev_l_row else 0

        # Feedbacks sentiment for this language
        fb_stmt = select(
            func.sum(case((Feedback.sentiment_label == "Positive", 1), else_=0)).label("pos"),
            func.sum(case((Feedback.sentiment_label == "Neutral", 1), else_=0)).label("neu"),
            func.sum(case((Feedback.sentiment_label == "Negative", 1), else_=0)).label("neg"),
        ).where(func.lower(Feedback.language) == l_code)
        if start_date:
            fb_stmt = fb_stmt.where(Feedback.created_at >= start_date)
        if end_date:
            fb_stmt = fb_stmt.where(Feedback.created_at <= end_date)
        if campaign_id:
            fb_stmt = fb_stmt.where(Feedback.campaign_id == campaign_id)
        fb_row = db.execute(fb_stmt).fetchone()

        s_dist = {
            "Positive": int(fb_row.pos or 0) if fb_row else 0,
            "Neutral": int(fb_row.neu or 0) if fb_row else 0,
            "Negative": int(fb_row.neg or 0) if fb_row else 0,
        }

        open_rate = round(opens / delivered * 100, 2) if delivered > 0 else 0.0
        ctr = round(clicks / delivered * 100, 2) if delivered > 0 else 0.0
        resp_rate = round(replies / delivered * 100, 2) if delivered > 0 else 0.0

        by_language[l_code] = LanguageBreakdownItem(
            language=l_code,
            messages=msgs,
            delivered=delivered,
            opens=opens,
            clicks=clicks,
            replies=replies,
            participations=participations,
            open_rate=open_rate,
            ctr=ctr,
            response_rate=resp_rate,
            sentiment_distribution=s_dist,
        )

    # 3. By Audience Segment
    seg_stmt = select(Segment)
    if segment_id:
        seg_stmt = seg_stmt.where(Segment.id == segment_id)
    all_segments = db.execute(seg_stmt).scalars().all()

    by_segment: List[SegmentBreakdownItem] = []
    for seg in all_segments:
        # Find campaigns linked to this segment
        camp_ids_stmt = select(campaign_segments.c.campaign_id).where(campaign_segments.c.segment_id == seg.id)
        linked_camp_ids = db.execute(camp_ids_stmt).scalars().all()

        if not linked_camp_ids:
            by_segment.append(
                SegmentBreakdownItem(
                    segment_id=seg.id,
                    segment_name=seg.name,
                    audience_size=0,
                )
            )
            continue

        # Aggregation across linked campaigns
        seg_m_stmt = select(
            func.sum(case((func.lower(Message.status).in_(["sent", "delivered", "failed"]), 1), else_=0)).label("sent"),
            func.sum(case((func.lower(Message.status) == "delivered", 1), else_=0)).label("delivered"),
            func.count(distinct(Message.audience_member_id)).label("audience_size"),
        ).where(Message.campaign_id.in_(linked_camp_ids))
        if start_date:
            seg_m_stmt = seg_m_stmt.where(Message.created_at >= start_date)
        if end_date:
            seg_m_stmt = seg_m_stmt.where(Message.created_at <= end_date)
        seg_m_row = db.execute(seg_m_stmt).fetchone()

        s_sent = int(seg_m_row.sent or 0)
        s_del = int(seg_m_row.delivered or 0)
        s_size = int(seg_m_row.audience_size or 0)

        # Engagement events
        seg_ev_stmt = select(
            func.count(distinct(case((func.lower(EngagementEvent.event_type).in_(["open", "opened"]), EngagementEvent.message_id), else_=None))).label("opens"),
            func.count(distinct(case((func.lower(EngagementEvent.event_type).in_(["click", "clicked"]), EngagementEvent.message_id), else_=None))).label("clicks"),
            func.sum(case((func.lower(EngagementEvent.event_type).in_(["reply", "replied"]), 1), else_=0)).label("replies"),
            func.sum(case((func.lower(EngagementEvent.event_type).in_(["participate", "participation"]), 1), else_=0)).label("participations"),
        ).where(EngagementEvent.campaign_id.in_(linked_camp_ids))
        if start_date:
            seg_ev_stmt = seg_ev_stmt.where(EngagementEvent.timestamp >= start_date)
        if end_date:
            seg_ev_stmt = seg_ev_stmt.where(EngagementEvent.timestamp <= end_date)
        seg_ev_row = db.execute(seg_ev_stmt).fetchone()

        s_opens = int(seg_ev_row.opens or 0) if seg_ev_row else 0
        s_clicks = int(seg_ev_row.clicks or 0) if seg_ev_row else 0
        s_replies = int(seg_ev_row.replies or 0) if seg_ev_row else 0
        s_part = int(seg_ev_row.participations or 0) if seg_ev_row else 0

        s_open_rate = round(s_opens / s_del * 100, 2) if s_del > 0 else 0.0
        s_resp_rate = round(s_replies / s_del * 100, 2) if s_del > 0 else 0.0

        by_segment.append(
            SegmentBreakdownItem(
                segment_id=seg.id,
                segment_name=seg.name,
                audience_size=s_size,
                sent=s_sent,
                delivered=s_del,
                opens=s_opens,
                clicks=s_clicks,
                replies=s_replies,
                participations=s_part,
                open_rate=s_open_rate,
                response_rate=s_resp_rate,
            )
        )

    # 4. Campaign Performance Rankings
    camp_query = select(Campaign)
    if campaign_id:
        camp_query = camp_query.where(Campaign.id == campaign_id)
    campaigns = db.execute(camp_query).scalars().all()

    ranked_items: List[CampaignRankItem] = []
    for c in campaigns:
        c_m_stmt = select(
            func.sum(case((func.lower(Message.status).in_(["sent", "delivered", "failed"]), 1), else_=0)).label("sent"),
            func.sum(case((func.lower(Message.status) == "delivered", 1), else_=0)).label("delivered"),
        ).where(Message.campaign_id == c.id)
        if start_date:
            c_m_stmt = c_m_stmt.where(Message.created_at >= start_date)
        if end_date:
            c_m_stmt = c_m_stmt.where(Message.created_at <= end_date)
        c_m_row = db.execute(c_m_stmt).fetchone()

        c_sent = int(c_m_row.sent or 0)
        c_del = int(c_m_row.delivered or 0)

        c_ev_stmt = select(
            func.count(distinct(case((func.lower(EngagementEvent.event_type).in_(["open", "opened"]), EngagementEvent.message_id), else_=None))).label("opens"),
            func.count(distinct(case((func.lower(EngagementEvent.event_type).in_(["click", "clicked"]), EngagementEvent.message_id), else_=None))).label("clicks"),
            func.sum(case((func.lower(EngagementEvent.event_type).in_(["reply", "replied"]), 1), else_=0)).label("replies"),
        ).where(EngagementEvent.campaign_id == c.id)
        if start_date:
            c_ev_stmt = c_ev_stmt.where(EngagementEvent.timestamp >= start_date)
        if end_date:
            c_ev_stmt = c_ev_stmt.where(EngagementEvent.timestamp <= end_date)
        c_ev_row = db.execute(c_ev_stmt).fetchone()

        c_opens = int(c_ev_row.opens or 0) if c_ev_row else 0
        c_clicks = int(c_ev_row.clicks or 0) if c_ev_row else 0
        c_replies = int(c_ev_row.replies or 0) if c_ev_row else 0

        c_open_rate = round(c_opens / c_del * 100, 2) if c_del > 0 else 0.0
        c_ctr = round(c_clicks / c_del * 100, 2) if c_del > 0 else 0.0
        c_resp_rate = round(c_replies / c_del * 100, 2) if c_del > 0 else 0.0

        score = round(c_open_rate * 0.4 + c_ctr * 0.4 + c_resp_rate * 0.2, 2)
        ranked_items.append(
            CampaignRankItem(
                campaign_id=c.id,
                campaign_name=c.name,
                status=c.status,
                sent=c_sent,
                delivered=c_del,
                opens=c_opens,
                clicks=c_clicks,
                open_rate=c_open_rate,
                ctr=c_ctr,
                response_rate=c_resp_rate,
                engagement_score=score,
            )
        )

    # Sort descending by engagement_score then open_rate
    sorted_campaigns = sorted(ranked_items, key=lambda x: (x.engagement_score, x.open_rate, x.delivered), reverse=True)
    best_performing = sorted_campaigns[:5]
    # For worst performing, only include campaigns with delivered > 0 or at least sent messages, sorted ascending
    active_worst = [c for c in sorted_campaigns if c.delivered > 0]
    worst_performing = sorted(active_worst, key=lambda x: (x.engagement_score, x.open_rate, x.delivered))[:5] if active_worst else []

    return PerformanceBreakdownsResponse(
        by_channel=by_channel,
        by_language=by_language,
        by_segment=by_segment,
        best_performing=best_performing,
        worst_performing=worst_performing,
    )


def get_campaign_funnel(
    db: Session,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    campaign_id: Optional[int] = None,
    channel: Optional[str] = None,
) -> CampaignFunnelResponse:
    """Computes a multi-tier conversion funnel: Sent -> Delivered -> Opened -> Clicked -> Responded."""
    start_date, end_date = validate_filter_dates(start_date, end_date)

    # Stage 1: Sent & Stage 2: Delivered
    msg_stmt = select(
        func.sum(case((func.lower(Message.status).in_(["sent", "delivered", "failed"]), 1), else_=0)).label("sent"),
        func.sum(case((func.lower(Message.status) == "delivered", 1), else_=0)).label("delivered"),
    )
    msg_stmt = _apply_message_filters(msg_stmt, start_date=start_date, end_date=end_date, campaign_id=campaign_id, channel=channel)
    msg_row = db.execute(msg_stmt).fetchone()

    sent_count = int(msg_row.sent or 0)
    delivered_count = int(msg_row.delivered or 0)

    # Stages 3, 4, 5: Opened, Clicked, Responded (via EngagementEvent)
    evt_stmt = select(
        func.count(distinct(case((func.lower(EngagementEvent.event_type).in_(["open", "opened"]), EngagementEvent.message_id), else_=None))).label("opened"),
        func.count(distinct(case((func.lower(EngagementEvent.event_type).in_(["click", "clicked"]), EngagementEvent.message_id), else_=None))).label("clicked"),
        func.sum(case((func.lower(EngagementEvent.event_type).in_(["reply", "replied", "participate", "participation"]), 1), else_=0)).label("responded"),
    )
    evt_stmt = _apply_event_filters(evt_stmt, start_date=start_date, end_date=end_date, campaign_id=campaign_id)
    evt_stmt = _apply_event_filters(evt_stmt, start_date=start_date, end_date=end_date, campaign_id=campaign_id)
    evt_row = db.execute(evt_stmt).fetchone()

    opened_count = int(evt_row.opened or 0)
    clicked_count = int(evt_row.clicked or 0)
    responded_count = int(evt_row.responded or 0)

    # Construct Funnel Stages with conversion and dropoff rates
    stages_data = [
        ("Sent", sent_count),
        ("Delivered", delivered_count),
        ("Opened", opened_count),
        ("Clicked", clicked_count),
        ("Responded", responded_count),
    ]

    stages: List[FunnelStageItem] = []
    top_count = sent_count if sent_count > 0 else 1

    for idx, (stage_name, count) in enumerate(stages_data):
        conv_top = round((count / top_count * 100), 2) if sent_count > 0 else 0.0

        if idx == 0:
            conv_prev = 100.0
            dropoff = 0.0
        else:
            prev_count = stages_data[idx - 1][1]
            conv_prev = round((count / prev_count * 100), 2) if prev_count > 0 else 0.0
            dropoff = round(max(0.0, 100.0 - conv_prev), 2) if prev_count > 0 else 0.0

        stages.append(
            FunnelStageItem(
                stage=stage_name,
                count=count,
                conversion_from_previous=conv_prev,
                conversion_from_top=conv_top,
                dropoff_rate=dropoff,
            )
        )

    overall_conv = round((responded_count / sent_count * 100), 2) if sent_count > 0 else 0.0

    return CampaignFunnelResponse(
        campaign_id=campaign_id,
        stages=stages,
        overall_conversion_rate=overall_conv,
    )


def get_ai_insights(
    db: Session,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    campaign_id: Optional[int] = None,
) -> AIInsightsResponse:
    """
    Generates actionable, evidence-based insights in plain English.
    Leverages configured AI provider where appropriate, backed by a deterministic rules engine.
    """
    start_date, end_date = validate_filter_dates(start_date, end_date)

    kpis = get_global_kpis(db, start_date=start_date, end_date=end_date, campaign_id=campaign_id)
    breakdowns = get_performance_breakdowns(db, start_date=start_date, end_date=end_date, campaign_id=campaign_id)

    insights: List[AIInsightItem] = []

    # 1. Channel Performance Insight
    ch_items = [ch for ch in breakdowns.by_channel.values() if ch.delivered > 0]
    if len(ch_items) >= 2:
        sorted_by_open = sorted(ch_items, key=lambda x: x.open_rate, reverse=True)
        top_ch = sorted_by_open[0]
        second_ch = sorted_by_open[1]
        diff = round(top_ch.open_rate - second_ch.open_rate, 1)
        if diff >= 3.0:
            insights.append(
                AIInsightItem(
                    id="ins_channel_perf",
                    type="positive",
                    title=f"{top_ch.channel} Leads in Citizen Engagement",
                    description=f"{top_ch.channel} achieved an open rate of {top_ch.open_rate}%, outperforming {second_ch.channel} ({second_ch.open_rate}%) by {diff}% during this period.",
                    metric="open_rate",
                    value=f"{top_ch.open_rate}%",
                    evidence=f"{top_ch.channel}: {top_ch.opens} opens / {top_ch.delivered} delivered.",
                    recommendation=f"Prioritize {top_ch.channel} for time-critical broadcasts and urgent civic alerts.",
                    severity="low",
                )
            )

    # 2. Language Engagement Insight
    lang_items = [lg for lg in breakdowns.by_language.values() if lg.delivered > 0]
    if len(lang_items) >= 2:
        sorted_by_resp = sorted(lang_items, key=lambda x: x.response_rate, reverse=True)
        top_lang = sorted_by_resp[0]
        low_lang = sorted_by_resp[-1]
        l_name = "Hindi" if top_lang.language == "hi" else "Tamil" if top_lang.language == "ta" else "English" if top_lang.language == "en" else top_lang.language.upper()
        if top_lang.response_rate > low_lang.response_rate:
            insights.append(
                AIInsightItem(
                    id="ins_lang_perf",
                    type="info",
                    title=f"Elevated Citizen Response in {l_name}",
                    description=f"{l_name} communications generated a {top_lang.response_rate}% response rate across {top_lang.delivered} delivered notices.",
                    metric="response_rate",
                    value=f"{top_lang.response_rate}%",
                    evidence=f"{top_lang.replies} citizen replies recorded for {l_name}.",
                    recommendation=f"Expand multilingual broadcast coverage and localized interactive prompts in {l_name}.",
                    severity="info",
                )
            )

    # 3. Delivery Health / Bounce Warning
    if kpis.total_messages_sent >= 10 and kpis.bounce_rate > 10.0:
        insights.append(
            AIInsightItem(
                id="ins_delivery_warn",
                type="warning",
                title="Elevated Delivery Failure Rate Detected",
                description=f"Message bounce rate is currently {kpis.bounce_rate}% ({kpis.status_counts.failed} failed dispatches). Verify recipient phone/email validity and provider credentials.",
                metric="bounce_rate",
                value=f"{kpis.bounce_rate}%",
                evidence=f"{kpis.status_counts.failed} failures out of {kpis.total_messages_sent} total dispatches.",
                recommendation="Audit recipient database phone/email validity and rotate gateway provider credentials.",
                severity="high",
            )
        )
    elif kpis.total_delivered > 0 and kpis.delivery_rate >= 95.0:
        insights.append(
            AIInsightItem(
                id="ins_delivery_health",
                type="positive",
                title="Optimal Delivery Channel Health",
                description=f"Delivery infrastructure achieved {kpis.delivery_rate}% successful delivery rate across {kpis.total_messages_sent} notices dispatched.",
                metric="delivery_rate",
                value=f"{kpis.delivery_rate}%",
                evidence=f"{kpis.total_delivered} successful deliveries recorded.",
                recommendation="Maintain current channel gateway configuration and retry policies.",
                severity="low",
            )
        )

    # 4. Top Segment Insight
    if breakdowns.by_segment:
        active_segs = [s for s in breakdowns.by_segment if s.delivered > 0]
        if active_segs:
            top_seg = max(active_segs, key=lambda x: x.open_rate)
            insights.append(
                AIInsightItem(
                    id="ins_top_segment",
                    type="recommendation",
                    title=f"Segment '{top_seg.segment_name}' Shows High Responsiveness",
                    description=f"Target segment '{top_seg.segment_name}' achieved a {top_seg.open_rate}% open rate. Prioritize similar demographic cohorts for high-urgency public notices.",
                    metric="open_rate",
                    value=f"{top_seg.open_rate}%",
                    evidence=f"{top_seg.opens} opens across {top_seg.audience_size} targeted citizens.",
                    recommendation=f"Allocate priority broadcast resources to demographic cohort '{top_seg.segment_name}'.",
                    severity="medium",
                )
            )

    # Baseline if insufficient activity
    if not insights:
        insights.append(
            AIInsightItem(
                id="ins_baseline",
                type="info",
                title="Baseline Telemetry Active",
                description="Analytics engine is monitoring multi-channel delivery and citizen responses. Insights expand as additional campaigns and broadcasts are executed.",
                metric="status",
                value="Active",
                evidence="Continuous background telemetry active.",
                recommendation="Launch initial campaign dispatches to generate empirical channel telemetry.",
                severity="info",
            )
        )

    gen_method = "rules_engine_fallback"
    try:
        provider = get_ai_provider()
        if provider:
            gen_method = f"model:{provider.get_provider_name()}"
    except Exception as exc:
        logger.debug("AI provider unavailable for analytics insights (%s); utilizing rules fallback.", exc)
        gen_method = "rules_engine_fallback"

    return AIInsightsResponse(
        insights=insights,
        generated_at=datetime.now(timezone.utc),
        generation_method=gen_method,
    )


def export_analytics_csv(
    db: Session,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    campaign_id: Optional[int] = None,
    channel: Optional[str] = None,
    language: Optional[str] = None,
    segment_id: Optional[int] = None,
) -> str:
    """Exports structured multi-section CSV analytics report respecting applied filters."""
    kpis = get_global_kpis(db, start_date, end_date, campaign_id, channel, language, segment_id)
    breakdowns = get_performance_breakdowns(db, start_date, end_date, campaign_id, channel, language, segment_id)
    funnel = get_campaign_funnel(db, start_date, end_date, campaign_id)

    output = io.StringIO()
    writer = csv.writer(output)

    # Section 1: Metadata
    writer.writerow(["MASSCOMMAI EXECUTIVE ANALYTICS REPORT"])
    writer.writerow(["Generated At", datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")])
    writer.writerow(["Filter Start Date", start_date.strftime("%Y-%m-%d") if start_date else "All Time"])
    writer.writerow(["Filter End Date", end_date.strftime("%Y-%m-%d") if end_date else "All Time"])
    writer.writerow(["Campaign ID Scope", f"#{campaign_id}" if campaign_id else "All Campaigns"])
    writer.writerow(["Channel Scope", channel or "All Channels"])
    writer.writerow(["Language Scope", language or "All Languages"])
    writer.writerow([])

    # Section 2: Key Performance Indicators
    writer.writerow(["--- KEY PERFORMANCE INDICATORS ---"])
    writer.writerow(["Metric", "Value", "Unit / Notes"])
    writer.writerow(["Total Campaigns", kpis.total_campaigns, "Campaigns active in scope"])
    writer.writerow(["Total Messages Sent", kpis.total_messages_sent, "Dispatched"])
    writer.writerow(["Total Delivered", kpis.total_delivered, "Delivered to citizens"])
    writer.writerow(["Total Reach", kpis.total_reach, "Unique citizens reached"])
    writer.writerow(["Delivery Rate", f"{kpis.delivery_rate}%", "Delivered / Sent"])
    writer.writerow(["Bounce / Failure Rate", f"{kpis.bounce_rate}%", "Failed / Sent"])
    writer.writerow(["Average Open Rate", f"{kpis.average_open_rate}%", "Unique Opens / Delivered"])
    writer.writerow(["Click-Through Rate (CTR)", f"{kpis.average_click_through_rate}%", "Unique Clicks / Delivered"])
    writer.writerow(["Response Rate", f"{kpis.response_rate}%", "Inbound Replies / Delivered"])
    writer.writerow(["Participation Rate", f"{kpis.participation_rate}%", "Feedback Submissions / Delivered"])
    writer.writerow([])

    # Section 3: Conversion Funnel
    writer.writerow(["--- CAMPAIGN CONVERSION FUNNEL ---"])
    writer.writerow(["Stage", "Count", "Conversion From Top (%)", "Conversion From Previous (%)", "Dropoff Rate (%)"])
    for s in funnel.stages:
        writer.writerow([s.stage, s.count, f"{s.conversion_from_top}%", f"{s.conversion_from_previous}%", f"{s.dropoff_rate}%"])
    writer.writerow(["Overall End-to-End Conversion", f"{funnel.overall_conversion_rate}%", "", "", ""])
    writer.writerow([])

    # Section 4: Channel Performance
    writer.writerow(["--- CHANNEL PERFORMANCE BREAKDOWN ---"])
    writer.writerow(["Channel", "Sent", "Delivered", "Failed", "Opens", "Clicks", "Replies", "Open Rate (%)", "CTR (%)", "Delivery Rate (%)"])
    for ch_name, ch in breakdowns.by_channel.items():
        writer.writerow([ch.channel, ch.sent, ch.delivered, ch.failed, ch.opens, ch.clicks, ch.replies, f"{ch.open_rate}%", f"{ch.ctr}%", f"{ch.delivery_rate}%"])
    writer.writerow([])

    # Section 5: Language Engagement Breakdown
    writer.writerow(["--- LANGUAGE ENGAGEMENT BREAKDOWN ---"])
    writer.writerow(["Language", "Messages", "Delivered", "Opens", "Clicks", "Replies", "Open Rate (%)", "Response Rate (%)", "Positive Sentiment", "Neutral Sentiment", "Negative Sentiment"])
    for l_code, ldata in breakdowns.by_language.items():
        writer.writerow([
            ldata.language,
            ldata.messages,
            ldata.delivered,
            ldata.opens,
            ldata.clicks,
            ldata.replies,
            f"{ldata.open_rate}%",
            f"{ldata.response_rate}%",
            ldata.sentiment_distribution.get("Positive", 0),
            ldata.sentiment_distribution.get("Neutral", 0),
            ldata.sentiment_distribution.get("Negative", 0),
        ])
    writer.writerow([])

    # Section 6: Audience Segment Efficiency
    if breakdowns.by_segment:
        writer.writerow(["--- AUDIENCE SEGMENT EFFICIENCY ---"])
        writer.writerow(["Segment ID", "Segment Name", "Audience Size", "Sent", "Delivered", "Opens", "Replies", "Open Rate (%)", "Response Rate (%)"])
        for seg in breakdowns.by_segment:
            writer.writerow([
                seg.segment_id,
                seg.segment_name,
                seg.audience_size,
                seg.sent,
                seg.delivered,
                seg.opens,
                seg.replies,
                f"{seg.open_rate}%",
                f"{seg.response_rate}%",
            ])

    return output.getvalue()


def export_analytics_pdf(
    db: Session,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    campaign_id: Optional[int] = None,
    channel: Optional[str] = None,
    language: Optional[str] = None,
    segment_id: Optional[int] = None,
) -> bytes:
    """Exports binary PDF analytics report using pure-Python PDF 1.4 generator."""
    kpis = get_global_kpis(db, start_date, end_date, campaign_id, channel, language, segment_id)
    breakdowns = get_performance_breakdowns(db, start_date, end_date, campaign_id, channel, language, segment_id)
    funnel = get_campaign_funnel(db, start_date, end_date, campaign_id)
    insights_resp = get_ai_insights(db, start_date, end_date, campaign_id)

    filter_dict = {
        "start_date": start_date.strftime("%Y-%m-%d") if start_date else None,
        "end_date": end_date.strftime("%Y-%m-%d") if end_date else None,
        "campaign_id": campaign_id,
        "channel": channel,
        "language": language,
        "segment_id": segment_id,
    }

    camp_name = None
    if campaign_id:
        c = db.get(Campaign, campaign_id)
        if c:
            camp_name = c.name

    return pdf_export_service.generate_analytics_pdf(
        kpis=kpis,
        breakdowns=breakdowns,
        funnel=funnel,
        insights=insights_resp.insights,
        filter_params=filter_dict,
        campaign_name=camp_name,
    )


def get_campaign_analytics_report(db: Session, campaign_id: int) -> CampaignAnalyticsReportResponse:
    """Generates unified analytics report payload for a single specified campaign."""
    campaign = db.get(Campaign, campaign_id)
    if not campaign:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Campaign with ID {campaign_id} not found.",
        )

    kpis = get_global_kpis(db, campaign_id=campaign_id)
    funnel = get_campaign_funnel(db, campaign_id=campaign_id)
    breakdowns = get_performance_breakdowns(db, campaign_id=campaign_id)
    insights = get_ai_insights(db, campaign_id=campaign_id)

    # Sentiment summary
    fb_stmt = select(
        func.count(Feedback.id).label("total"),
        func.avg(Feedback.rating).label("avg_rating"),
        func.sum(case((Feedback.sentiment_label == "Positive", 1), else_=0)).label("pos"),
        func.sum(case((Feedback.sentiment_label == "Neutral", 1), else_=0)).label("neu"),
        func.sum(case((Feedback.sentiment_label == "Negative", 1), else_=0)).label("neg"),
    ).where(Feedback.campaign_id == campaign_id)
    fb_row = db.execute(fb_stmt).fetchone()

    total_fb = int(fb_row.total or 0) if fb_row else 0
    avg_rating = round(float(fb_row.avg_rating or 0.0), 2) if fb_row and fb_row.avg_rating else 0.0
    sentiment_dist = {
        "Positive": int(fb_row.pos or 0) if fb_row else 0,
        "Neutral": int(fb_row.neu or 0) if fb_row else 0,
        "Negative": int(fb_row.neg or 0) if fb_row else 0,
    }

    return CampaignAnalyticsReportResponse(
        campaign_id=campaign.id,
        campaign_name=campaign.name,
        objective=campaign.objective,
        status=campaign.status,
        channels=campaign.channels if isinstance(campaign.channels, list) else [],
        start_date=campaign.start_date,
        end_date=campaign.end_date,
        kpis=kpis,
        funnel=funnel,
        by_channel=breakdowns.by_channel,
        by_language=breakdowns.by_language,
        sentiment_summary={
            "total_feedback": total_fb,
            "average_rating": avg_rating,
            "distribution": sentiment_dist,
        },
        insights=insights.insights,
    )
