"""Campaign Engagement and Audience Analytics Service.

Provides:
1. Direct recording of open, click, reply, and participate interaction events.
2. High-precision engagement metric aggregations (Open Rate, CTR, Response Rate, Participation Rate).
3. Consistent denominator calculation (total delivered messages, avoiding failed or unsent counts).
4. Sentiment distributions and channel/language breakdowns with zero-denominator safety.
"""

from __future__ import annotations
import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Tuple

from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select, func, and_, distinct

from app.models.campaign import Campaign
from app.models.communication import Message, Feedback
from app.models.engagement import EngagementEvent, TrackedLink
from app.schemas.engagement import (
    CampaignEngagementMetricsResponse,
    ChannelEngagementMetrics,
    LanguageEngagementMetrics,
    SentimentBreakdown,
    KeywordSummary,
    TopicSummary,
    EngagementEventResponse,
)
from app.services import sentiment_service

logger = logging.getLogger("masscommai.engagement")


def record_engagement_event(
    db: Session,
    campaign_id: int,
    event_type: str,
    message_id: Optional[int] = None,
    audience_member_id: Optional[int] = None,
    device_info: Optional[str] = None,
    language: Optional[str] = "en",
    link_url: Optional[str] = None,
    metadata_json: Optional[Dict[str, Any]] = None,
) -> EngagementEvent:
    """Creates and persists an EngagementEvent audit record."""
    now_utc = datetime.now(timezone.utc)

    # If message is provided, resolve missing campaign/audience member
    if message_id and not audience_member_id:
        msg = db.get(Message, message_id)
        if msg:
            campaign_id = msg.campaign_id
            audience_member_id = msg.audience_member_id
            language = msg.language or language
            if event_type == "open" and not msg.opened_at:
                msg.opened_at = now_utc

    event = EngagementEvent(
        campaign_id=campaign_id,
        message_id=message_id,
        audience_member_id=audience_member_id,
        event_type=event_type,
        timestamp=now_utc,
        device_info=device_info,
        language=language,
        link_url=link_url,
        metadata_json=metadata_json or {},
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def get_campaign_engagement_metrics(
    db: Session,
    campaign_id: int,
) -> CampaignEngagementMetricsResponse:
    """
    Computes rigorous engagement metrics for an approved or completed campaign.
    Guarantees meaningful denominators:
    - Open Rate = Unique Opens / Delivered Messages
    - CTR = Unique Clicks / Delivered Messages
    - Response Rate = Inbound Replies / Delivered Messages
    - Participation Rate = Feedback Submissions / Delivered Messages
    Safely handles empty campaigns and zero denominators.
    """
    camp = db.get(Campaign, campaign_id)
    if not camp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Campaign #{campaign_id} not found.",
        )

    # 1. Total and Delivered Messages
    msg_stmt = select(Message).where(Message.campaign_id == campaign_id)
    all_messages = list(db.execute(msg_stmt).scalars().all())

    total_messages = len(all_messages)
    delivered_msgs = [m for m in all_messages if m.status == "Delivered"]
    total_delivered = len(delivered_msgs)

    # 2. Engagement Events for Campaign
    events_stmt = (
        select(EngagementEvent)
        .where(EngagementEvent.campaign_id == campaign_id)
        .order_by(EngagementEvent.timestamp.desc())
    )
    all_events = list(db.execute(events_stmt).scalars().all())

    open_events = [e for e in all_events if e.event_type == "open"]
    click_events = [e for e in all_events if e.event_type == "click"]
    reply_events = [e for e in all_events if e.event_type == "reply"]
    part_events = [e for e in all_events if e.event_type == "participate"]

    total_opens = len(open_events)
    unique_opens = len({e.message_id for e in open_events if e.message_id})
    # If opened_at is set directly on message, also ensure counted
    for m in delivered_msgs:
        if m.opened_at:
            unique_opens = max(unique_opens, len({m.id for m in delivered_msgs if m.opened_at}))

    total_clicks = len(click_events)
    unique_clicks = len({e.message_id for e in click_events if e.message_id})

    replies_count = len(reply_events)
    participations_count = len(part_events)

    # 3. Calculate Rates with Zero-Division Protection
    open_rate = round(float(unique_opens / total_delivered), 4) if total_delivered > 0 else 0.0
    ctr = round(float(unique_clicks / total_delivered), 4) if total_delivered > 0 else 0.0
    click_to_open = round(float(unique_clicks / unique_opens), 4) if unique_opens > 0 else 0.0
    response_rate = round(float(replies_count / total_delivered), 4) if total_delivered > 0 else 0.0
    participation_rate = round(float(participations_count / total_delivered), 4) if total_delivered > 0 else 0.0

    # 4. Sentiment Analysis & Distribution
    fb_stmt = select(Feedback).where(Feedback.campaign_id == campaign_id)
    all_feedbacks = list(db.execute(fb_stmt).scalars().all())

    # Include reply texts in sentiment & topic pool
    sentiment_pool: List[Tuple[Optional[str], Optional[float]]] = []
    text_corpus: List[str] = []

    for f in all_feedbacks:
        sentiment_pool.append((f.sentiment_label, f.sentiment_score))
        if f.comment:
            text_corpus.append(f.comment)

    for r in reply_events:
        txt = (r.metadata_json or {}).get("reply_text") or (r.metadata_json or {}).get("body")
        if txt:
            text_corpus.append(txt)
            saved_label = (r.metadata_json or {}).get("sentiment")
            saved_score = (r.metadata_json or {}).get("score")
            if saved_label and saved_score is not None:
                sentiment_pool.append((saved_label, saved_score))
            else:
                lbl, sc = sentiment_service.analyze_sentiment(txt, r.language)
                sentiment_pool.append((lbl, sc))

    pos_cnt = sum(1 for lbl, _ in sentiment_pool if lbl == "Positive")
    neu_cnt = sum(1 for lbl, _ in sentiment_pool if lbl == "Neutral")
    neg_cnt = sum(1 for lbl, _ in sentiment_pool if lbl == "Negative")
    total_sentiment = len(sentiment_pool)

    avg_score = (
        round(sum(sc for _, sc in sentiment_pool if sc is not None) / total_sentiment, 3)
        if total_sentiment > 0
        else 0.0
    )

    sentiment_dist = SentimentBreakdown(
        positive=pos_cnt,
        neutral=neu_cnt,
        negative=neg_cnt,
        positive_pct=round((pos_cnt / total_sentiment) * 100.0, 1) if total_sentiment > 0 else 0.0,
        neutral_pct=round((neu_cnt / total_sentiment) * 100.0, 1) if total_sentiment > 0 else 0.0,
        negative_pct=round((neg_cnt / total_sentiment) * 100.0, 1) if total_sentiment > 0 else 0.0,
        average_score=avg_score,
    )

    # Average rating from feedback
    ratings = [f.rating for f in all_feedbacks if f.rating is not None]
    avg_rating = round(float(sum(ratings) / len(ratings)), 2) if ratings else 0.0

    # 5. Breakdown by Channel
    by_channel: Dict[str, ChannelEngagementMetrics] = {}
    standard_channels = ["Email", "SMS", "WhatsApp", "Push", "Web"]

    for ch in standard_channels:
        ch_msgs = [m for m in all_messages if m.channel and m.channel.lower() == ch.lower()]
        ch_deliv = [m for m in ch_msgs if m.status == "Delivered"]
        ch_deliv_cnt = len(ch_deliv)
        ch_msg_ids = {m.id for m in ch_msgs}

        ch_opens = len([e for e in open_events if e.message_id in ch_msg_ids])
        ch_clicks = len([e for e in click_events if e.message_id in ch_msg_ids])
        ch_replies = len([e for e in reply_events if e.message_id in ch_msg_ids])

        ch_open_rate = round(float(ch_opens / ch_deliv_cnt), 4) if ch_deliv_cnt > 0 else 0.0
        ch_ctr = round(float(ch_clicks / ch_deliv_cnt), 4) if ch_deliv_cnt > 0 else 0.0

        by_channel[ch] = ChannelEngagementMetrics(
            channel=ch,
            sent=len(ch_msgs),
            delivered=ch_deliv_cnt,
            opens=ch_opens,
            clicks=ch_clicks,
            replies=ch_replies,
            open_rate=ch_open_rate,
            ctr=ch_ctr,
        )

    # 6. Breakdown by Language
    by_language: Dict[str, LanguageEngagementMetrics] = {}
    all_langs = {m.language for m in all_messages if m.language} or {"en"}

    for lg in sorted(all_langs):
        lg_msgs = [m for m in all_messages if m.language == lg]
        lg_deliv = [m for m in lg_msgs if m.status == "Delivered"]
        lg_deliv_cnt = len(lg_deliv)
        lg_msg_ids = {m.id for m in lg_msgs}

        lg_opens = len([e for e in open_events if e.message_id in lg_msg_ids])
        lg_clicks = len([e for e in click_events if e.message_id in lg_msg_ids])
        lg_replies = len([e for e in reply_events if e.message_id in lg_msg_ids])

        lg_open_rate = round(float(lg_opens / lg_deliv_cnt), 4) if lg_deliv_cnt > 0 else 0.0

        by_language[lg] = LanguageEngagementMetrics(
            language=lg,
            delivered=lg_deliv_cnt,
            opens=lg_opens,
            clicks=lg_clicks,
            replies=lg_replies,
            open_rate=lg_open_rate,
        )

    # 7. Topic & Keyword Detection
    nlp_summary = sentiment_service.extract_topics_and_keywords(text_corpus)
    top_keywords = [KeywordSummary(keyword=item["keyword"], count=item["count"]) for item in nlp_summary["keywords"][:10]]
    top_topics = [TopicSummary(topic=item["topic"], count=item["count"]) for item in nlp_summary["topics"]]
    common_questions = nlp_summary["common_questions"]
    concerns = nlp_summary["concerns"]

    # 8. Recent Engagement Events
    recent_events = [
        EngagementEventResponse.model_validate(e)
        for e in all_events[:20]
    ]

    return CampaignEngagementMetricsResponse(
        campaign_id=camp.id,
        campaign_name=camp.name,
        total_messages=total_messages,
        total_delivered=total_delivered,
        unique_opens=unique_opens,
        total_opens=total_opens,
        open_rate=open_rate,
        unique_clicks=unique_clicks,
        total_clicks=total_clicks,
        click_through_rate=ctr,
        click_to_open_rate=click_to_open,
        replies_count=replies_count,
        response_rate=response_rate,
        participations_count=participations_count,
        participation_rate=participation_rate,
        average_rating=avg_rating,
        sentiment_distribution=sentiment_dist,
        by_channel=by_channel,
        by_language=by_language,
        top_keywords=top_keywords,
        top_topics=top_topics,
        common_questions=common_questions,
        concerns=concerns,
        recent_events=recent_events,
    )
