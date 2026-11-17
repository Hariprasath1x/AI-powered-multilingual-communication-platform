"""Pydantic v2 schemas for Task 16: Engagement Tracking, Feedback, and Sentiment Analysis."""

from __future__ import annotations
from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, HttpUrl


class TrackedLinkCreateRequest(BaseModel):
    """Payload to register an outbound URL for click tracking."""
    original_url: str = Field(..., max_length=2048, description="Target redirect destination URL")
    campaign_id: int = Field(..., description="Associated campaign ID")
    message_id: Optional[int] = Field(None, description="Optional associated message ID")


class TrackedLinkResponse(BaseModel):
    """Structured response for a tracked link."""
    id: int
    link_id: str
    campaign_id: int
    message_id: Optional[int] = None
    original_url: str
    click_count: int
    is_active: bool
    created_at: datetime
    last_clicked_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class EngagementEventResponse(BaseModel):
    """Audited citizen engagement interaction event."""
    id: int
    campaign_id: int
    message_id: Optional[int] = None
    audience_member_id: Optional[int] = None
    event_type: str
    timestamp: datetime
    device_info: Optional[str] = None
    language: Optional[str] = "en"
    link_url: Optional[str] = None
    metadata_json: Optional[Dict[str, Any]] = None

    model_config = {"from_attributes": True}


class PublicFeedbackInfoResponse(BaseModel):
    """Public presentation payload for the citizen feedback form (zero PII exposure)."""
    campaign_id: int
    campaign_name: str
    campaign_objective: Optional[str] = None
    feedback_token: str
    preferred_language: str = "en"
    channels: List[str] = Field(default_factory=list)


class PublicFeedbackSubmissionRequest(BaseModel):
    """Public citizen feedback payload."""
    feedback_token: str = Field(..., min_length=6, max_length=128, description="Unguessable feedback tracking token")
    rating: int = Field(..., ge=1, le=5, description="1 to 5 star rating")
    comment: Optional[str] = Field(None, max_length=2000, description="Optional citizen comment")
    language: Optional[str] = Field("en", max_length=10, description="Language code")


class FeedbackResponse(BaseModel):
    """Confirmation response upon feedback submission."""
    id: int
    campaign_id: int
    message_id: Optional[int] = None
    rating: Optional[int] = None
    comment: Optional[str] = None
    sentiment_label: Optional[str] = None
    sentiment_score: Optional[float] = None
    language: Optional[str] = None
    channel: Optional[str] = "Web"
    is_resolved: bool = False
    created_at: datetime

    model_config = {"from_attributes": True}


class FeedbackDetailResponse(BaseModel):
    """Detailed administrative view of citizen feedback."""
    id: int
    campaign_id: int
    campaign_name: Optional[str] = None
    message_id: Optional[int] = None
    audience_member_id: Optional[int] = None
    recipient_name: Optional[str] = None
    recipient_contact: Optional[str] = None
    rating: Optional[int] = None
    comment: Optional[str] = None
    sentiment_label: Optional[str] = None
    sentiment_score: Optional[float] = None
    language: Optional[str] = None
    channel: Optional[str] = "Web"
    is_resolved: bool = False
    resolution_notes: Optional[str] = None
    resolved_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class FeedbackListResponse(BaseModel):
    """Paginated list of feedback records with administrative summary."""
    items: List[FeedbackDetailResponse]
    total: int
    positive_count: int
    neutral_count: int
    negative_count: int
    average_rating: float


class FeedbackResolveRequest(BaseModel):
    """Payload to mark citizen feedback as resolved."""
    resolution_notes: Optional[str] = Field(None, max_length=1000, description="Action taken or response summary")


class FeedbackReplyRequest(BaseModel):
    """Payload to dispatch a follow-up reply to a citizen's feedback/reply."""
    reply_text: str = Field(..., min_length=2, max_length=1000, description="Response message body")
    channel_override: Optional[str] = Field(None, description="Optional channel override (SMS, Email, WhatsApp)")


class FeedbackReplyResponse(BaseModel):
    """Outcome of administrative reply dispatch."""
    success: bool
    feedback_id: int
    channel: str
    recipient: str
    detail: str


class KeywordSummary(BaseModel):
    keyword: str
    count: int


class TopicSummary(BaseModel):
    topic: str
    count: int


class SentimentBreakdown(BaseModel):
    positive: int = 0
    neutral: int = 0
    negative: int = 0
    positive_pct: float = 0.0
    neutral_pct: float = 0.0
    negative_pct: float = 0.0
    average_score: float = 0.0


class ChannelEngagementMetrics(BaseModel):
    channel: str
    sent: int = 0
    delivered: int = 0
    opens: int = 0
    clicks: int = 0
    replies: int = 0
    open_rate: float = 0.0
    ctr: float = 0.0


class LanguageEngagementMetrics(BaseModel):
    language: str
    delivered: int = 0
    opens: int = 0
    clicks: int = 0
    replies: int = 0
    open_rate: float = 0.0


class CampaignEngagementMetricsResponse(BaseModel):
    """Aggregated campaign engagement and sentiment metrics."""
    campaign_id: int
    campaign_name: str
    total_messages: int
    total_delivered: int
    unique_opens: int
    total_opens: int
    open_rate: float
    unique_clicks: int
    total_clicks: int
    click_through_rate: float
    click_to_open_rate: float
    replies_count: int
    response_rate: float
    participations_count: int
    participation_rate: float
    average_rating: float
    sentiment_distribution: SentimentBreakdown
    by_channel: Dict[str, ChannelEngagementMetrics]
    by_language: Dict[str, LanguageEngagementMetrics]
    top_keywords: List[KeywordSummary]
    top_topics: List[TopicSummary]
    common_questions: List[str]
    concerns: List[str]
    recent_events: List[EngagementEventResponse] = Field(default_factory=list)
