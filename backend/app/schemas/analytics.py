"""Pydantic v2 schemas for Milestone 3, Task 17: Analytics Dashboards & Reporting."""

from __future__ import annotations
from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field


class StatusCounts(BaseModel):
    """Message delivery status aggregation."""
    sent: int = 0
    delivered: int = 0
    failed: int = 0
    pending: int = 0


class GlobalKPIsResponse(BaseModel):
    """Global system or filtered dashboard Key Performance Indicators."""
    total_campaigns: int = Field(0, description="Total number of campaigns active in scope")
    total_messages_sent: int = Field(0, description="Messages with status Sent or Delivered")
    total_delivered: int = Field(0, description="Messages successfully delivered to citizens")
    total_reach: int = Field(0, description="Unique audience members reached")
    average_open_rate: float = Field(0.0, description="Unique opens / delivered percentage")
    average_click_through_rate: float = Field(0.0, description="Unique clicks / delivered percentage")
    response_rate: float = Field(0.0, description="Inbound replies / delivered percentage")
    participation_rate: float = Field(0.0, description="Feedback submissions / delivered percentage")
    status_counts: StatusCounts = Field(default_factory=StatusCounts)
    delivery_rate: float = Field(0.0, description="Delivered / total sent percentage")
    bounce_rate: float = Field(0.0, description="Failed / total sent percentage")


class TrendDataPoint(BaseModel):
    """Aggregate engagement count for a discrete time bucket."""
    date: str = Field(..., description="ISO Date string (YYYY-MM-DD)")
    sent: int = 0
    delivered: int = 0
    opens: int = 0
    clicks: int = 0
    replies: int = 0
    participations: int = 0


class EngagementTrendsResponse(BaseModel):
    """Time-series engagement trends over the requested window."""
    interval: str = Field("daily", description="Aggregation bucket: daily, weekly, or monthly")
    start_date: str
    end_date: str
    trends: List[TrendDataPoint] = Field(default_factory=list)


class ChannelBreakdownItem(BaseModel):
    """Aggregated performance metrics for a communication channel."""
    channel: str
    sent: int = 0
    delivered: int = 0
    failed: int = 0
    opens: int = 0
    clicks: int = 0
    replies: int = 0
    open_rate: float = 0.0
    ctr: float = 0.0
    delivery_rate: float = 0.0


class LanguageBreakdownItem(BaseModel):
    """Aggregated performance metrics for a recipient or campaign language."""
    language: str
    messages: int = 0
    delivered: int = 0
    opens: int = 0
    clicks: int = 0
    replies: int = 0
    participations: int = 0
    open_rate: float = 0.0
    ctr: float = 0.0
    response_rate: float = 0.0
    engagement_score: float = 0.0
    sentiment_distribution: Dict[str, int] = Field(default_factory=lambda: {"Positive": 0, "Neutral": 0, "Negative": 0})


class SegmentBreakdownItem(BaseModel):
    """Audience segment delivery and engagement efficiency."""
    segment_id: int
    segment_name: str
    audience_size: int = 0
    sent: int = 0
    delivered: int = 0
    opens: int = 0
    clicks: int = 0
    replies: int = 0
    participations: int = 0
    open_rate: float = 0.0
    response_rate: float = 0.0
    engagement_score: float = 0.0


class CampaignRankItem(BaseModel):
    """Ranked campaign performance item."""
    campaign_id: int
    campaign_name: str
    status: str
    sent: int = 0
    delivered: int = 0
    opens: int = 0
    clicks: int = 0
    open_rate: float = 0.0
    ctr: float = 0.0
    response_rate: float = 0.0
    engagement_score: float = 0.0


class PerformanceBreakdownsResponse(BaseModel):
    """Comprehensive performance breakdowns across channels, languages, segments, and campaigns."""
    by_channel: Dict[str, ChannelBreakdownItem] = Field(default_factory=dict)
    by_language: Dict[str, LanguageBreakdownItem] = Field(default_factory=dict)
    by_segment: List[SegmentBreakdownItem] = Field(default_factory=list)
    best_performing: List[CampaignRankItem] = Field(default_factory=list)
    worst_performing: List[CampaignRankItem] = Field(default_factory=list)


class FunnelStageItem(BaseModel):
    """Conversion funnel stage statistics."""
    stage: str
    count: int = 0
    conversion_from_previous: float = 0.0
    conversion_from_top: float = 0.0
    dropoff_rate: float = 0.0


class CampaignFunnelResponse(BaseModel):
    """Multi-stage conversion funnel: Sent -> Delivered -> Opened -> Clicked -> Responded."""
    campaign_id: Optional[int] = None
    stages: List[FunnelStageItem] = Field(default_factory=list)
    overall_conversion_rate: float = 0.0


class AIInsightItem(BaseModel):
    """Evidence-based plain English analytical insight."""
    id: str
    type: str = Field(..., description="positive, warning, info, recommendation")
    title: str
    description: str
    metric: Optional[str] = None
    value: Optional[str] = None
    evidence: Optional[str] = None
    recommendation: Optional[str] = None
    severity: Optional[str] = Field("info", description="low, medium, high, info")


class AIInsightsResponse(BaseModel):
    """Collection of actionable evidence-based AI insights."""
    insights: List[AIInsightItem] = Field(default_factory=list)
    generated_at: datetime
    generation_method: str = Field(..., description="model:name or rules_engine_fallback")


class CampaignAnalyticsReportResponse(BaseModel):
    """Unified single-campaign reporting payload."""
    campaign_id: int
    campaign_name: str
    objective: Optional[str] = None
    status: str
    channels: List[str] = Field(default_factory=list)
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    kpis: GlobalKPIsResponse
    funnel: CampaignFunnelResponse
    by_channel: Dict[str, ChannelBreakdownItem] = Field(default_factory=dict)
    by_language: Dict[str, LanguageBreakdownItem] = Field(default_factory=dict)
    sentiment_summary: Dict[str, Any] = Field(default_factory=dict)
    insights: List[AIInsightItem] = Field(default_factory=list)
