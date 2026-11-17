"""Analytics and Reporting Router for Milestone 3, Task 17."""

from __future__ import annotations
import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query, Path, Response, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.dependencies import require_role
from app.models.user import User
from app.schemas.analytics import (
    GlobalKPIsResponse,
    EngagementTrendsResponse,
    PerformanceBreakdownsResponse,
    CampaignFunnelResponse,
    AIInsightsResponse,
    CampaignAnalyticsReportResponse,
)
from app.services import analytics_service

logger = logging.getLogger("masscommai.analytics")

router = APIRouter(
    prefix="/analytics",
    tags=["Analytics & Reporting"],
)

ANALYTICS_ROLES = ["Admin", "Campaign Manager", "Communication Team"]


@router.get(
    "/kpis",
    response_model=GlobalKPIsResponse,
    summary="Get aggregated global or filtered campaign KPIs",
)
def get_global_kpis_endpoint(
    start_date: Optional[str] = Query(None, description="Start date filter (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date filter (YYYY-MM-DD)"),
    campaign_id: Optional[int] = Query(None, description="Filter by campaign ID"),
    channel: Optional[str] = Query(None, description="Filter by channel (Email, SMS, WhatsApp, Push, Web Broadcast)"),
    language: Optional[str] = Query(None, description="Filter by language code (en, hi, ta, te, mr, kn)"),
    segment_id: Optional[int] = Query(None, description="Filter by audience segment ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(ANALYTICS_ROLES)),
):
    """
    Returns global or filtered KPIs including total messages, delivered, reach,
    open rate, click-through rate, response rate, participation rate, and delivery breakdown.
    Zero-division safe with empty state fallbacks.
    """
    start_dt, end_dt = analytics_service.validate_filter_dates(start_date, end_date)
    return analytics_service.get_global_kpis(
        db=db,
        start_date=start_dt,
        end_date=end_dt,
        campaign_id=campaign_id,
        channel=channel,
        language=language,
        segment_id=segment_id,
    )


@router.get(
    "/trends",
    response_model=EngagementTrendsResponse,
    summary="Get aggregated engagement trends time-series",
)
def get_engagement_trends_endpoint(
    start_date: Optional[str] = Query(None, description="Start date filter (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date filter (YYYY-MM-DD)"),
    campaign_id: Optional[int] = Query(None, description="Filter by campaign ID"),
    channel: Optional[str] = Query(None, description="Filter by channel"),
    interval: str = Query("daily", pattern="^(daily|weekly|monthly)$", description="Aggregation interval"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(ANALYTICS_ROLES)),
):
    """
    Returns time-series engagement metrics (messages sent, delivered, opened, clicked, responded)
    bucketed across continuous daily/weekly/monthly dates.
    """
    start_dt, end_dt = analytics_service.validate_filter_dates(start_date, end_date)
    return analytics_service.get_engagement_trends(
        db=db,
        start_date=start_dt,
        end_date=end_dt,
        campaign_id=campaign_id,
        channel=channel,
        interval=interval,
    )


@router.get(
    "/breakdowns",
    response_model=PerformanceBreakdownsResponse,
    summary="Get multi-dimensional performance breakdowns",
)
def get_performance_breakdowns_endpoint(
    start_date: Optional[str] = Query(None, description="Start date filter (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date filter (YYYY-MM-DD)"),
    campaign_id: Optional[int] = Query(None, description="Filter by campaign ID"),
    channel: Optional[str] = Query(None, description="Filter by channel"),
    language: Optional[str] = Query(None, description="Filter by language"),
    segment_id: Optional[int] = Query(None, description="Filter by segment ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(ANALYTICS_ROLES)),
):
    """
    Returns performance breakdowns across:
    - Channels (Email, SMS, WhatsApp, Push, Web Broadcast)
    - Content Languages (Sent, Opens, CTR, Response Rate, Sentiment)
    - Audience Segments
    - Best and Worst Performing Campaigns
    """
    start_dt, end_dt = analytics_service.validate_filter_dates(start_date, end_date)
    return analytics_service.get_performance_breakdowns(
        db=db,
        start_date=start_dt,
        end_date=end_dt,
        campaign_id=campaign_id,
        channel=channel,
        language=language,
        segment_id=segment_id,
    )


@router.get(
    "/funnel",
    response_model=CampaignFunnelResponse,
    summary="Get campaign conversion funnel stages",
)
def get_campaign_funnel_endpoint(
    campaign_id: Optional[int] = Query(None, description="Filter by campaign ID"),
    start_date: Optional[str] = Query(None, description="Start date filter (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date filter (YYYY-MM-DD)"),
    channel: Optional[str] = Query(None, description="Filter by channel"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(ANALYTICS_ROLES)),
):
    """
    Returns 5-stage conversion funnel:
    Sent -> Delivered -> Opened -> Clicked -> Responded
    with absolute counts, top-conversion %, step-conversion %, and dropoff rates.
    """
    start_dt, end_dt = analytics_service.validate_filter_dates(start_date, end_date)
    return analytics_service.get_campaign_funnel(
        db=db,
        start_date=start_dt,
        end_date=end_dt,
        campaign_id=campaign_id,
        channel=channel,
    )


@router.get(
    "/insights",
    response_model=AIInsightsResponse,
    summary="Get AI / rules-based actionable insights and recommendations",
)
def get_ai_insights_endpoint(
    campaign_id: Optional[int] = Query(None, description="Filter by campaign ID"),
    start_date: Optional[str] = Query(None, description="Start date filter (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date filter (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(ANALYTICS_ROLES)),
):
    """
    Generates plain-English, evidence-backed actionable insights and recommendations
    comparing channel open rates, language response rates, delivery warnings,
    and top-performing audience segments.
    """
    start_dt, end_dt = analytics_service.validate_filter_dates(start_date, end_date)
    return analytics_service.get_ai_insights(
        db=db,
        start_date=start_dt,
        end_date=end_dt,
        campaign_id=campaign_id,
    )


@router.get(
    "/export/csv",
    summary="Export analytics report as structured CSV file",
)
def export_analytics_csv_endpoint(
    start_date: Optional[str] = Query(None, description="Start date filter (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date filter (YYYY-MM-DD)"),
    campaign_id: Optional[int] = Query(None, description="Filter by campaign ID"),
    channel: Optional[str] = Query(None, description="Filter by channel"),
    language: Optional[str] = Query(None, description="Filter by language"),
    segment_id: Optional[int] = Query(None, description="Filter by segment ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(ANALYTICS_ROLES)),
):
    """
    Exports a structured multi-section CSV report containing Metadata, KPIs,
    Conversion Funnel, Channel Performance, and Multilingual Engagement.
    """
    start_dt, end_dt = analytics_service.validate_filter_dates(start_date, end_date)
    csv_content = analytics_service.export_analytics_csv(
        db=db,
        start_date=start_dt,
        end_date=end_dt,
        campaign_id=campaign_id,
        channel=channel,
        language=language,
        segment_id=segment_id,
    )

    filename = f"analytics_report_{start_date or 'all'}_to_{end_date or 'current'}.csv"
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-cache, no-store, must-revalidate",
        },
    )


@router.get(
    "/export/pdf",
    summary="Export analytics executive summary as PDF document",
)
def export_analytics_pdf_endpoint(
    start_date: Optional[str] = Query(None, description="Start date filter (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date filter (YYYY-MM-DD)"),
    campaign_id: Optional[int] = Query(None, description="Filter by campaign ID"),
    channel: Optional[str] = Query(None, description="Filter by channel"),
    language: Optional[str] = Query(None, description="Filter by language"),
    segment_id: Optional[int] = Query(None, description="Filter by segment ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(ANALYTICS_ROLES)),
):
    """
    Exports an executive-ready PDF report containing KPI metrics, conversion funnel,
    channel distribution, multilingual engagement, and actionable insights.
    Zero C-binary dependencies (pure Python PDF generator).
    """
    start_dt, end_dt = analytics_service.validate_filter_dates(start_date, end_date)
    pdf_bytes = analytics_service.export_analytics_pdf(
        db=db,
        start_date=start_dt,
        end_date=end_dt,
        campaign_id=campaign_id,
        channel=channel,
        language=language,
        segment_id=segment_id,
    )

    filename = f"analytics_report_{start_date or 'all'}_to_{end_date or 'current'}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-cache, no-store, must-revalidate",
        },
    )


@router.get(
    "/campaign-report/{campaign_id}",
    response_model=CampaignAnalyticsReportResponse,
    summary="Get comprehensive unified analytics report for a single campaign",
)
def get_campaign_analytics_report_endpoint(
    campaign_id: int = Path(..., ge=1, description="Campaign ID to inspect"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(ANALYTICS_ROLES)),
):
    """
    Returns complete analytics dossier for a specific campaign: metadata, KPIs,
    conversion funnel, channel breakdown, language metrics, sentiment distribution,
    and plain-English recommendations.
    """
    return analytics_service.get_campaign_analytics_report(db=db, campaign_id=campaign_id)
