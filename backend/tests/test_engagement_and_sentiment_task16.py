"""Automated Unit and Integration Tests for Milestone 3, Task 16:
Engagement Tracking, Feedback Collection & Sentiment Analysis.

Covers:
1. Open tracking event creation (GET /webhooks/open/{tracking_id})
2. Click tracking and safe redirection (GET /r/{link_id})
3. Invalid and malicious redirect rejection (open-redirect vulnerability protection)
4. Inbound WhatsApp reply event ingestion
5. Inbound SMS reply event ingestion
6. Webhook event deduplication (idempotency via WebhookEvent)
7. Public feedback token validation and zero-PII info API (GET /feedback/info/{token})
8. Public feedback submission validation (1-5 stars, content constraints)
9. Duplicate feedback submission rejection
10. Sentiment classification and score storage (Positive, Neutral, Negative, [-1.0, 1.0])
11. AI provider fallback and deterministic offline evaluation
12. Topic, keyword, question, and concern extraction
13. Campaign engagement metrics API (GET /campaigns/{id}/engagement)
14. Channel and language filtering for feedback
15. Zero-denominator and empty campaign safety (no ZeroDivisionError)
16. Administrative feedback resolution workflow (POST /feedback/{id}/resolve)
17. Administrative feedback reply dispatch with consent verification (POST /feedback/{id}/reply)
18. Role-based access control on administrative engagement endpoints
"""

import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone
import json
import asyncio

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.main import app
from app.db.base import Base
from app.db.session import get_db
from app.core.security import create_access_token, get_password_hash
from app.models.user import User, Role
from app.models.campaign import Campaign
from app.models.audience import AudienceMember
from app.models.communication import Message, Feedback, DeliveryLog
from app.models.channel_config import ChannelConfiguration
from app.models.engagement import TrackedLink, EngagementEvent
from app.models.webhook_event import WebhookEvent
from app.services import sentiment_service, link_tracking_service, engagement_service, feedback_service


def seed_roles(db):
    roles = [
        Role(id=1, name="Admin", description="Administrator"),
        Role(id=2, name="Campaign Manager", description="Campaign Manager"),
        Role(id=3, name="Communication Team", description="Communication Team"),
    ]
    for r in roles:
        if not db.get(Role, r.id):
            db.add(r)
    db.commit()


class TestEngagementAndSentimentTask16(unittest.TestCase):
    """Full unit and integration test suite for Task 16."""

    def setUp(self):
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=self.engine)
        self.SessionLocal = sessionmaker(
            autocommit=False, autoflush=False, bind=self.engine, expire_on_commit=False
        )
        self.db = self.SessionLocal()

        def override_get_db():
            try:
                yield self.db
            finally:
                pass

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)

        # Seed data
        seed_roles(self.db)

        # Users
        self.admin_user = User(
            id=1,
            full_name="Admin Officer",
            email="admin@masscomm.gov.in",
            hashed_password=get_password_hash("AdminPass123!"),
            role_id=1,
            is_active=True,
        )
        self.manager_user = User(
            id=2,
            full_name="Manager Officer",
            email="manager@masscomm.gov.in",
            hashed_password=get_password_hash("ManagerPass123!"),
            role_id=2,
            is_active=True,
        )
        self.db.add(self.admin_user)
        self.db.add(self.manager_user)

        # Audience Members
        self.citizen_consented = AudienceMember(
            id=101,
            name="Aarav Sharma",
            email="aarav.sharma@example.gov.in",
            phone="+919876543210",
            preferred_language="en",
            preferred_channel="SMS",
            consent_status=True,
        )
        self.citizen_unconsented = AudienceMember(
            id=102,
            name="Bhavna Patel",
            email="bhavna.patel@example.gov.in",
            phone="+919876543211",
            preferred_language="hi",
            preferred_channel="Email",
            consent_status=False,  # Revoked / unconsented
        )
        self.db.add(self.citizen_consented)
        self.db.add(self.citizen_unconsented)

        # Approved Campaign
        self.campaign = Campaign(
            id=301,
            name="National Polio Immunization Drive",
            campaign_type="Awareness",
            priority="High",
            status="Approved",
            channels=["SMS", "Email", "WhatsApp"],
            created_by=self.manager_user.id,
        )
        self.db.add(self.campaign)

        # Messages (Delivered)
        self.msg_email = Message(
            id=501,
            tracking_id="trk_email_test_12345",
            feedback_token="fbt_email_test_12345",
            campaign_id=self.campaign.id,
            audience_member_id=self.citizen_consented.id,
            channel="Email",
            language="en",
            rendered_content="Please bring children under 5 to nearest polio booth.",
            status="Delivered",
            sent_at=datetime.now(timezone.utc),
            delivered_at=datetime.now(timezone.utc),
        )
        self.msg_sms = Message(
            id=502,
            tracking_id="trk_sms_test_67890",
            feedback_token="fbt_sms_test_67890",
            campaign_id=self.campaign.id,
            audience_member_id=self.citizen_consented.id,
            channel="SMS",
            language="hi",
            rendered_content="राष्ट्रीय पोलियो दिवस रविवार को है।",
            status="Delivered",
            sent_at=datetime.now(timezone.utc),
            delivered_at=datetime.now(timezone.utc),
        )
        self.msg_wa = Message(
            id=503,
            tracking_id="trk_wa_test_11223",
            feedback_token="fbt_wa_test_11223",
            campaign_id=self.campaign.id,
            audience_member_id=self.citizen_consented.id,
            channel="WhatsApp",
            language="en",
            rendered_content="Polio awareness message on WhatsApp.",
            status="Delivered",
            sent_at=datetime.now(timezone.utc),
            delivered_at=datetime.now(timezone.utc),
        )
        self.db.add(self.msg_email)
        self.db.add(self.msg_sms)
        self.db.add(self.msg_wa)

        # Default Channel Configurations
        ch_sms = ChannelConfiguration(
            channel="SMS",
            is_enabled=True,
            provider_type="mock",
            sender_address="+1555010022",
            sender_name="MassComm SMS",
            credentials={},
        )
        ch_email = ChannelConfiguration(
            channel="Email",
            is_enabled=True,
            provider_type="mock",
            sender_address="alerts@masscomm.gov.in",
            sender_name="MassComm Alerts",
            credentials={},
        )
        self.db.add(ch_sms)
        self.db.add(ch_email)

        self.db.commit()

        # Auth headers
        admin_token = create_access_token(self.admin_user.id)
        self.admin_headers = {"Authorization": f"Bearer {admin_token}"}
        manager_token = create_access_token(self.manager_user.id)
        self.manager_headers = {"Authorization": f"Bearer {manager_token}"}

    def tearDown(self):
        app.dependency_overrides.clear()
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)

    # -------------------------------------------------------------------------
    # 1. Open Tracking Event Creation
    # -------------------------------------------------------------------------
    def test_01_open_tracking_pixel_creates_engagement_event(self):
        """GET /webhooks/open/{tracking_id} records an 'open' EngagementEvent and sets opened_at."""
        resp = self.client.get(
            f"/webhooks/open/{self.msg_email.tracking_id}",
            headers={"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) Mobile"},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.headers["content-type"], "image/gif")

        # Verify Message.opened_at is updated
        self.db.refresh(self.msg_email)
        self.assertIsNotNone(self.msg_email.opened_at)

        # Verify EngagementEvent is created with device classification
        events = list(self.db.query(EngagementEvent).filter_by(
            message_id=self.msg_email.id,
            event_type="open",
        ).all())
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].device_info, "Mobile")
        self.assertEqual(events[0].campaign_id, self.campaign.id)

    # -------------------------------------------------------------------------
    # 2. Click Tracking and Safe Redirection
    # -------------------------------------------------------------------------
    def test_02_click_tracking_records_event_and_redirects(self):
        """GET /r/{link_id} records 'click' event, increments click_count, and returns HTTP 307 redirect."""
        tracked = link_tracking_service.create_tracked_link(
            db=self.db,
            campaign_id=self.campaign.id,
            original_url="https://mohfw.gov.in/polio-schedule",
            message_id=self.msg_email.id,
        )

        resp = self.client.get(
            f"/r/{tracked.link_id}",
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
            follow_redirects=False,
        )
        self.assertEqual(resp.status_code, 307)
        self.assertEqual(resp.headers["location"], "https://mohfw.gov.in/polio-schedule")

        # Verify click_count incremented
        self.db.refresh(tracked)
        self.assertEqual(tracked.click_count, 1)
        self.assertIsNotNone(tracked.last_clicked_at)

        # Verify engagement event recorded
        events = list(self.db.query(EngagementEvent).filter_by(
            message_id=self.msg_email.id,
            event_type="click",
        ).all())
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].link_url, "https://mohfw.gov.in/polio-schedule")
        self.assertEqual(events[0].device_info, "Desktop")

    # -------------------------------------------------------------------------
    # 3. Invalid and Malicious Redirect Rejection (Open Redirect Vulnerability Guard)
    # -------------------------------------------------------------------------
    def test_03_malicious_redirect_urls_rejected(self):
        """Rejects javascript:, data:, file:, CRLF, and relative bypasses."""
        malicious_urls = [
            "javascript:alert('xss')",
            "data:text/html,<script>alert(1)</script>",
            "file:///etc/passwd",
            "ftp://malicious.org/payload",
            "https://mohfw.gov.in/\r\nSet-Cookie: admin=true",
            "/relative/path/bypass",
            "",
        ]
        for bad_url in malicious_urls:
            with self.subTest(bad_url=bad_url):
                with self.assertRaises(Exception):
                    link_tracking_service.create_tracked_link(
                        db=self.db,
                        campaign_id=self.campaign.id,
                        original_url=bad_url,
                    )

    # -------------------------------------------------------------------------
    # 4. Inbound WhatsApp Reply Ingestion
    # -------------------------------------------------------------------------
    def test_04_inbound_whatsapp_reply_ingestion_and_sentiment(self):
        """Inbound WhatsApp webhook records a 'reply' event and feedback with sentiment."""
        payload = {
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "messages": [
                                    {
                                        "id": "wamid_inbound_001",
                                        "from": "+919876543210",
                                        "text": {"body": "Thank you, the polio booth staff was very polite and helpful!"},
                                    }
                                ]
                            }
                        }
                    ]
                }
            ]
        }
        resp = self.client.post("/webhooks/whatsapp", json=payload)
        self.assertEqual(resp.status_code, 200)

        # Verify reply engagement event
        events = list(self.db.query(EngagementEvent).filter_by(event_type="reply").all())
        self.assertTrue(len(events) >= 1)
        self.assertEqual(events[0].device_info, "Mobile (WhatsApp)")

        # Verify feedback record with Positive sentiment
        fbs = list(self.db.query(Feedback).filter_by(channel="WhatsApp").all())
        self.assertTrue(len(fbs) >= 1)
        self.assertEqual(fbs[0].sentiment_label, "Positive")
        self.assertGreater(fbs[0].sentiment_score, 0.15)

    # -------------------------------------------------------------------------
    # 5. Inbound SMS Reply Ingestion
    # -------------------------------------------------------------------------
    def test_05_inbound_sms_reply_ingestion_and_sentiment(self):
        """Inbound SMS webhook records a 'reply' event and feedback with sentiment."""
        payload = {
            "From": "+919876543210",
            "Body": "Booth was closed when I arrived. Very bad experience and long delay.",
            "MessageSid": "sms_sid_unique_999",
        }
        resp = self.client.post("/webhooks/sms", json=payload)
        self.assertEqual(resp.status_code, 200)

        # Verify reply engagement event
        events = list(self.db.query(EngagementEvent).filter_by(
            event_type="reply",
            device_info="Mobile (SMS)",
        ).all())
        self.assertEqual(len(events), 1)

        # Verify feedback with Negative sentiment
        fbs = list(self.db.query(Feedback).filter_by(channel="SMS").all())
        self.assertEqual(len(fbs), 1)
        self.assertEqual(fbs[0].sentiment_label, "Negative")
        self.assertLess(fbs[0].sentiment_score, -0.15)

    # -------------------------------------------------------------------------
    # 6. Webhook Deduplication (Idempotency via WebhookEvent)
    # -------------------------------------------------------------------------
    def test_06_duplicate_webhook_reply_is_idempotently_ignored(self):
        """Identical webhook event ID is not processed twice."""
        payload = {
            "From": "+919876543210",
            "Body": "Great initiative!",
            "MessageSid": "duplicate_test_sid_123",
        }
        resp1 = self.client.post("/webhooks/sms", json=payload)
        self.assertEqual(resp1.status_code, 200)

        initial_count = self.db.query(Feedback).filter_by(channel="SMS").count()

        # Send same payload second time
        resp2 = self.client.post("/webhooks/sms", json=payload)
        self.assertEqual(resp2.status_code, 200)
        self.assertEqual(resp2.json()["status"], "already_processed")

        final_count = self.db.query(Feedback).filter_by(channel="SMS").count()
        self.assertEqual(initial_count, final_count)

    # -------------------------------------------------------------------------
    # 7. Public Feedback Token Validation and Zero-PII Info API
    # -------------------------------------------------------------------------
    def test_07_public_feedback_info_returns_campaign_metadata_without_pii(self):
        """GET /feedback/info/{token} returns public campaign metadata with zero PII exposure."""
        resp = self.client.get(f"/feedback/info/{self.msg_email.feedback_token}")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["campaign_id"], self.campaign.id)
        self.assertEqual(data["campaign_name"], self.campaign.name)
        self.assertEqual(data["feedback_token"], self.msg_email.feedback_token)
        # Ensure citizen PII is NOT in response
        self.assertNotIn("email", data)
        self.assertNotIn("phone", data)
        self.assertNotIn("recipient_name", data)

        # Invalid token returns 404
        resp_invalid = self.client.get("/feedback/info/fbt_nonexistent_token_99999")
        self.assertEqual(resp_invalid.status_code, 404)

    # -------------------------------------------------------------------------
    # 8. Public Feedback Submission Validation
    # -------------------------------------------------------------------------
    def test_08_public_feedback_submission_validation(self):
        """POST /feedback/submit validates star rating 1-5 and comment bounds."""
        # Valid 5-star submission
        valid_payload = {
            "feedback_token": self.msg_email.feedback_token,
            "rating": 5,
            "comment": "Doctor was very professional and teeka was given quickly.",
            "language": "en",
        }
        resp = self.client.post("/feedback/submit", json=valid_payload)
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertEqual(data["rating"], 5)
        self.assertEqual(data["sentiment_label"], "Positive")
        self.assertGreater(data["sentiment_score"], 0.15)

        # Invalid rating (0 or 6) returns 422
        bad_payload = {
            "feedback_token": self.msg_sms.feedback_token,
            "rating": 6,
        }
        resp_bad = self.client.post("/feedback/submit", json=bad_payload)
        self.assertEqual(resp_bad.status_code, 422)

    # -------------------------------------------------------------------------
    # 9. Duplicate Feedback Submission Rejection
    # -------------------------------------------------------------------------
    def test_09_duplicate_feedback_submission_rejected(self):
        """Submitting feedback twice for the same notification token returns HTTP 400."""
        payload = {
            "feedback_token": self.msg_sms.feedback_token,
            "rating": 4,
            "comment": "Acha prabandh tha.",
            "language": "hi",
        }
        resp1 = self.client.post("/feedback/submit", json=payload)
        self.assertEqual(resp1.status_code, 201)

        # Second submission with same token
        resp2 = self.client.post("/feedback/submit", json=payload)
        self.assertEqual(resp2.status_code, 400)
        self.assertIn("already been submitted", resp2.json()["detail"])

    # -------------------------------------------------------------------------
    # 10. Sentiment Classification and Score Storage
    # -------------------------------------------------------------------------
    def test_10_sentiment_classification_and_scoring(self):
        """Verifies Positive, Neutral, and Negative classifications across multilingual inputs."""
        test_cases = [
            ("The staff was great, smooth experience and very helpful!", "Positive", 0.15),
            ("Awful delay, long queue, and doctor was rude and unhelpful.", "Negative", -0.15),
            ("Booths will open at 9 am. Please check the timings.", "Neutral", 0.0),
            ("बढ़िया व्यवस्था और तुरंत टीका लग गया, धन्यवाद!", "Positive", 0.15),
            ("बहुत खराब व्यवस्था, भीड़ और परेशानी हुई।", "Negative", -0.15),
            ("", "Neutral", 0.0),
        ]
        for text, expected_label, threshold in test_cases:
            with self.subTest(text=text):
                label, score = sentiment_service.analyze_sentiment(text)
                self.assertEqual(label, expected_label)
                if expected_label == "Positive":
                    self.assertGreater(score, threshold)
                elif expected_label == "Negative":
                    self.assertLess(score, threshold)
                else:
                    self.assertGreaterEqual(score, -0.15)
                    self.assertLessEqual(score, 0.15)

    # -------------------------------------------------------------------------
    # 11. AI Provider Fallback and Offline Safety
    # -------------------------------------------------------------------------
    def test_11_ai_provider_failure_fallback(self):
        """Sentiment service operates deterministically without external network calls."""
        # Test malformed input, none, non-string safely handled
        label1, score1 = sentiment_service.analyze_sentiment(None)
        self.assertEqual(label1, "Neutral")
        self.assertEqual(score1, 0.0)

        label2, score2 = sentiment_service.analyze_sentiment("   \n\t  ")
        self.assertEqual(label2, "Neutral")
        self.assertEqual(score2, 0.0)

    # -------------------------------------------------------------------------
    # 12. Topic, Keyword, Question, and Concern Extraction
    # -------------------------------------------------------------------------
    def test_12_topic_and_keyword_extraction(self):
        """extract_topics_and_keywords identifies frequent topics, keywords, questions, and concerns."""
        feedback_corpus = [
            "What time will the polio booth close in Rohini sector 3?",
            "How can I register my newborn baby for the teeka?",
            "Staff was polite and vaccine drops were given smoothly.",
            "Long waiting queue at the center and no drinking water facility.",
            "Very good clinic center and helpful nurse.",
            "Kahan par booth lagega kal subah?",
        ]
        result = sentiment_service.extract_topics_and_keywords(feedback_corpus)

        self.assertTrue(len(result["keywords"]) > 0)
        self.assertTrue(len(result["topics"]) > 0)
        self.assertTrue(len(result["common_questions"]) >= 2)
        self.assertTrue(len(result["concerns"]) >= 1)

        # Questions contain question marks or question keywords
        self.assertTrue(any("?" in q for q in result["common_questions"]))

    # -------------------------------------------------------------------------
    # 13. Campaign Engagement Metrics API
    # -------------------------------------------------------------------------
    def test_13_campaign_engagement_metrics_api(self):
        """GET /campaigns/{id}/engagement computes accurate rates and breakdowns."""
        # Record open event
        engagement_service.record_engagement_event(
            db=self.db,
            campaign_id=self.campaign.id,
            message_id=self.msg_email.id,
            event_type="open",
        )
        # Record click event
        engagement_service.record_engagement_event(
            db=self.db,
            campaign_id=self.campaign.id,
            message_id=self.msg_email.id,
            event_type="click",
            link_url="https://mohfw.gov.in",
        )
        # Record feedback with sentiment
        fb = Feedback(
            campaign_id=self.campaign.id,
            audience_member_id=self.citizen_consented.id,
            message_id=self.msg_email.id,
            rating=5,
            comment="Excellent vaccination arrangements.",
            sentiment_label="Positive",
            sentiment_score=0.8,
            channel="Email",
            language="en",
        )
        self.db.add(fb)
        engagement_service.record_engagement_event(
            db=self.db,
            campaign_id=self.campaign.id,
            message_id=self.msg_email.id,
            event_type="participate",
        )
        self.db.commit()

        resp = self.client.get(
            f"/campaigns/{self.campaign.id}/engagement",
            headers=self.manager_headers,
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        self.assertEqual(data["campaign_id"], self.campaign.id)
        self.assertEqual(data["total_delivered"], 3)
        self.assertEqual(data["unique_opens"], 1)
        self.assertAlmostEqual(data["open_rate"], 1 / 3, places=2)
        self.assertEqual(data["unique_clicks"], 1)
        self.assertAlmostEqual(data["click_through_rate"], 1 / 3, places=2)
        self.assertEqual(data["participations_count"], 1)
        self.assertAlmostEqual(data["participation_rate"], 1 / 3, places=2)

        # Verify sentiment breakdown
        self.assertEqual(data["sentiment_distribution"]["positive"], 1)
        self.assertEqual(data["sentiment_distribution"]["positive_pct"], 100.0)

        # Verify by_channel metrics exist
        self.assertIn("Email", data["by_channel"])
        self.assertEqual(data["by_channel"]["Email"]["opens"], 1)

    # -------------------------------------------------------------------------
    # 14. Channel and Language Filtering for Feedback
    # -------------------------------------------------------------------------
    def test_14_feedback_listing_with_filters(self):
        """GET /feedback filters by sentiment, channel, and language."""
        fb_pos = Feedback(
            campaign_id=self.campaign.id,
            rating=5,
            comment="Bahut acha teekakaran kendra.",
            sentiment_label="Positive",
            sentiment_score=0.7,
            channel="SMS",
            language="hi",
        )
        fb_neg = Feedback(
            campaign_id=self.campaign.id,
            rating=1,
            comment="Very poor clinic organization.",
            sentiment_label="Negative",
            sentiment_score=-0.8,
            channel="Email",
            language="en",
        )
        self.db.add(fb_pos)
        self.db.add(fb_neg)
        self.db.commit()

        # Filter by Negative sentiment
        resp_neg = self.client.get("/feedback?sentiment=Negative", headers=self.manager_headers)
        self.assertEqual(resp_neg.status_code, 200)
        data_neg = resp_neg.json()
        self.assertEqual(len(data_neg["items"]), 1)
        self.assertEqual(data_neg["items"][0]["sentiment_label"], "Negative")

        # Filter by Hindi language
        resp_hi = self.client.get("/feedback?language=hi", headers=self.manager_headers)
        self.assertEqual(resp_hi.status_code, 200)
        data_hi = resp_hi.json()
        self.assertEqual(len(data_hi["items"]), 1)
        self.assertEqual(data_hi["items"][0]["language"], "hi")

    # -------------------------------------------------------------------------
    # 15. Zero-Denominator and Empty Campaign Safety
    # -------------------------------------------------------------------------
    def test_15_empty_campaign_engagement_metrics_returns_zeroes(self):
        """Campaign with zero messages returns zeroes without ZeroDivisionError."""
        empty_camp = Campaign(
            name="Empty Future Campaign",
            campaign_type="Awareness",
            priority="Low",
            status="Approved",
            channels=["SMS"],
            created_by=self.manager_user.id,
        )
        self.db.add(empty_camp)
        self.db.commit()

        resp = self.client.get(
            f"/campaigns/{empty_camp.id}/engagement",
            headers=self.manager_headers,
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["total_messages"], 0)
        self.assertEqual(data["total_delivered"], 0)
        self.assertEqual(data["open_rate"], 0.0)
        self.assertEqual(data["click_through_rate"], 0.0)
        self.assertEqual(data["response_rate"], 0.0)
        self.assertEqual(data["participation_rate"], 0.0)

    # -------------------------------------------------------------------------
    # 16. Administrative Feedback Resolution Workflow
    # -------------------------------------------------------------------------
    def test_16_resolve_feedback_workflow(self):
        """POST /feedback/{id}/resolve marks feedback resolved with action notes."""
        fb = Feedback(
            campaign_id=self.campaign.id,
            rating=2,
            comment="Vaccine was delayed by 1 hour.",
            sentiment_label="Negative",
            sentiment_score=-0.6,
            is_resolved=False,
        )
        self.db.add(fb)
        self.db.commit()

        payload = {"resolution_notes": "Contacted medical officer; supply chain issue resolved."}
        resp = self.client.post(
            f"/feedback/{fb.id}/resolve",
            json=payload,
            headers=self.manager_headers,
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["is_resolved"])
        self.assertIn("supply chain issue resolved", data["resolution_notes"])
        self.assertIsNotNone(data["resolved_at"])

    # -------------------------------------------------------------------------
    # 17. Administrative Feedback Reply with Consent Verification
    # -------------------------------------------------------------------------
    def test_17_reply_to_feedback_enforces_consent(self):
        """POST /feedback/{id}/reply dispatches response when consented, blocks when unconsented."""
        # 1. Consented citizen feedback
        fb_consented = Feedback(
            campaign_id=self.campaign.id,
            audience_member_id=self.citizen_consented.id,
            comment="Is there parking available near the center?",
            channel="SMS",
        )
        # 2. Unconsented citizen feedback
        fb_unconsented = Feedback(
            campaign_id=self.campaign.id,
            audience_member_id=self.citizen_unconsented.id,
            comment="Do not text me.",
            channel="Email",
        )
        self.db.add(fb_consented)
        self.db.add(fb_unconsented)
        self.db.commit()

        # Consented reply succeeds
        resp_ok = self.client.post(
            f"/feedback/{fb_consented.id}/reply",
            json={"reply_text": "Yes, parking is available at the school ground opposite the booth."},
            headers=self.manager_headers,
        )
        self.assertEqual(resp_ok.status_code, 200)
        self.assertTrue(resp_ok.json()["success"])

        # Unconsented reply is rejected with HTTP 400
        resp_blocked = self.client.post(
            f"/feedback/{fb_unconsented.id}/reply",
            json={"reply_text": "We apologize."},
            headers=self.manager_headers,
        )
        self.assertEqual(resp_blocked.status_code, 400)
        self.assertIn("consent", resp_blocked.json()["detail"].lower())

    # -------------------------------------------------------------------------
    # 18. Role-Based Access Control on Administrative Engagement Endpoints
    # -------------------------------------------------------------------------
    def test_18_rbac_on_administrative_endpoints(self):
        """Unauthenticated requests to admin engagement endpoints are rejected with 401."""
        resp_metrics = self.client.get(f"/campaigns/{self.campaign.id}/engagement")
        self.assertEqual(resp_metrics.status_code, 401)

        resp_feedback = self.client.get("/feedback")
        self.assertEqual(resp_feedback.status_code, 401)

        resp_topics = self.client.get("/feedback/topics")
        self.assertEqual(resp_topics.status_code, 401)

    # -------------------------------------------------------------------------
    # 19. Model-Based Sentiment Analysis (Positive, Neutral, Negative)
    # -------------------------------------------------------------------------
    def test_19_model_based_sentiment_positive_neutral_negative(self):
        """Verifies primary model-based analysis classifies Positive, Neutral, Negative with confidence."""
        sentiment_service.clear_sentiment_cache()

        pos_res = asyncio.run(sentiment_service.analyze_sentiment_model("Great work, very helpful and smooth service!"))
        self.assertEqual(pos_res.sentiment, "Positive")
        self.assertGreater(pos_res.score, 0.0)
        self.assertGreaterEqual(pos_res.confidence, 0.0)
        self.assertLessEqual(pos_res.confidence, 1.0)
        self.assertTrue(pos_res.method.startswith("model:"))

        neg_res = asyncio.run(sentiment_service.analyze_sentiment_model("Terrible delay and very rude behavior."))
        self.assertEqual(neg_res.sentiment, "Negative")
        self.assertLess(neg_res.score, 0.0)
        self.assertTrue(neg_res.method.startswith("model:"))

        neu_res = asyncio.run(sentiment_service.analyze_sentiment_model("The booth is open from 9 AM to 5 PM."))
        self.assertEqual(neu_res.sentiment, "Neutral")
        self.assertEqual(neu_res.score, 0.0)
        self.assertTrue(neu_res.method.startswith("model:"))

    # -------------------------------------------------------------------------
    # 20. Confidence and Score Validation and Normalization
    # -------------------------------------------------------------------------
    def test_20_confidence_and_score_validation_and_normalization(self):
        """Validates that out-of-range model scores and mixed-case labels are sanitized and clamped."""
        sentiment_service.clear_sentiment_cache()

        class MockProviderOutOfBounds:
            def get_provider_name(self):
                return "mock_test"
            async def analyze_sentiment(self, text, language="en"):
                from app.services.ai.base import SentimentAnalysisResult
                return SentimentAnalysisResult(
                    sentiment="positive",
                    score=2.85,
                    confidence=1.75,
                    method="model:mock_test",
                )

        res1 = asyncio.run(sentiment_service.analyze_sentiment_model("arbitrary text 1", provider=MockProviderOutOfBounds()))
        self.assertEqual(res1.sentiment, "Positive")
        self.assertEqual(res1.score, 1.0)
        self.assertEqual(res1.confidence, 1.0)

        class MockProviderNegativeOutOfBounds:
            def get_provider_name(self):
                return "mock_test"
            async def analyze_sentiment(self, text, language="en"):
                from app.services.ai.base import SentimentAnalysisResult
                return SentimentAnalysisResult(
                    sentiment="NEGATIVE",
                    score=-4.5,
                    confidence=-0.3,
                    method="model:mock_test",
                )

        res2 = asyncio.run(sentiment_service.analyze_sentiment_model("arbitrary text 2", provider=MockProviderNegativeOutOfBounds()))
        self.assertEqual(res2.sentiment, "Negative")
        self.assertEqual(res2.score, -1.0)
        self.assertEqual(res2.confidence, 0.0)

    # -------------------------------------------------------------------------
    # 21. Multilingual Model Sentiment (English, Hindi, Tamil)
    # -------------------------------------------------------------------------
    def test_21_multilingual_model_sentiment_english_hindi_tamil(self):
        """Verifies model-based sentiment across English, Hindi (Devanagari & Romanized), and Tamil."""
        sentiment_service.clear_sentiment_cache()

        # Hindi Devanagari positive
        hi_pos = asyncio.run(sentiment_service.analyze_sentiment_model("टीकाकरण केंद्र पर बहुत बढ़िया व्यवस्था और धन्यवाद", language="hi"))
        self.assertEqual(hi_pos.sentiment, "Positive")
        self.assertGreater(hi_pos.score, 0.0)

        # Hindi Romanized negative
        hi_neg = asyncio.run(sentiment_service.analyze_sentiment_model("Kharab vyavastha aur bahut deri hui", language="hi"))
        self.assertEqual(hi_neg.sentiment, "Negative")
        self.assertLess(hi_neg.score, 0.0)

        # Tamil positive
        ta_pos = asyncio.run(sentiment_service.analyze_sentiment_model("மிகவும் நல்ல சேவை மற்றும் நன்றி", language="ta"))
        self.assertEqual(ta_pos.sentiment, "Positive")
        self.assertGreater(ta_pos.score, 0.0)

        # Tamil negative
        ta_neg = asyncio.run(sentiment_service.analyze_sentiment_model("மோசம் மற்றும் தாமதம்", language="ta"))
        self.assertEqual(ta_neg.sentiment, "Negative")
        self.assertLess(ta_neg.score, 0.0)

    # -------------------------------------------------------------------------
    # 22. Invalid Model Response Triggers Deterministic Fallback
    # -------------------------------------------------------------------------
    def test_22_invalid_model_response_triggers_deterministic_fallback(self):
        """When model response is malformed or invalid, gracefully falls back to deterministic lexicon."""
        sentiment_service.clear_sentiment_cache()

        # [SIMULATE_INVALID_JSON] triggers malformed model response
        res = asyncio.run(sentiment_service.analyze_sentiment_model("Great doctor and helpful staff [SIMULATE_INVALID_JSON]"))
        self.assertEqual(res.sentiment, "Positive")
        self.assertGreater(res.score, 0.0)
        self.assertEqual(res.method, "lexicon_fallback")
        # Ensure fallback is never represented as model-generated
        self.assertFalse(res.method.startswith("model:"))

    # -------------------------------------------------------------------------
    # 23. Provider Timeout Triggers Deterministic Fallback
    # -------------------------------------------------------------------------
    def test_23_provider_timeout_triggers_deterministic_fallback(self):
        """When AI provider times out, gracefully falls back to deterministic lexicon."""
        sentiment_service.clear_sentiment_cache()

        # [SIMULATE_TIMEOUT] triggers AIProviderTimeoutError
        res = asyncio.run(sentiment_service.analyze_sentiment_model("Awful delay, horrible queue [SIMULATE_TIMEOUT]"))
        self.assertEqual(res.sentiment, "Negative")
        self.assertLess(res.score, 0.0)
        self.assertEqual(res.method, "lexicon_fallback")

    # -------------------------------------------------------------------------
    # 24. Feedback Submission & Inbound Replies Record Analysis Metadata
    # -------------------------------------------------------------------------
    def test_24_feedback_and_inbound_replies_record_model_analysis_metadata(self):
        """Verifies both web feedback and inbound webhook replies receive model analysis with recorded metadata."""
        sentiment_service.clear_sentiment_cache()

        # 1. Public feedback submission
        payload = {
            "feedback_token": self.msg_email.feedback_token,
            "rating": 5,
            "comment": "Super experience, doctor was very helpful and professional!",
            "language": "en",
        }
        resp = self.client.post("/feedback/submit", json=payload)
        self.assertEqual(resp.status_code, 201)

        event_part = (
            self.db.query(EngagementEvent)
            .filter(EngagementEvent.event_type == "participate")
            .order_by(EngagementEvent.id.desc())
            .first()
        )
        self.assertIsNotNone(event_part)
        self.assertIn("analysis_method", event_part.metadata_json)
        self.assertTrue(event_part.metadata_json["analysis_method"].startswith("model:"))
        self.assertIn("confidence", event_part.metadata_json)
        self.assertEqual(event_part.metadata_json["sentiment_label"], "Positive")

        # 2. Inbound SMS reply
        sms_payload = {
            "From": "+919876543210",
            "To": "+15551234567",
            "Body": "Terrible service, unhelpful and bad queue",
            "MessageSid": "SM_MODEL_TEST_999",
        }
        resp_sms = self.client.post("/webhooks/sms", json=sms_payload)
        self.assertEqual(resp_sms.status_code, 200)

        event_reply = (
            self.db.query(EngagementEvent)
            .filter(EngagementEvent.event_type == "reply", EngagementEvent.device_info == "Mobile (SMS)")
            .order_by(EngagementEvent.id.desc())
            .first()
        )
        self.assertIsNotNone(event_reply)
        self.assertIn("analysis_method", event_reply.metadata_json)
        self.assertTrue(event_reply.metadata_json["analysis_method"].startswith("model:"))
        self.assertEqual(event_reply.metadata_json["sentiment"], "Negative")

    # -------------------------------------------------------------------------
    # 25. Deduplication Cache Prevents Unnecessary Repeat Analysis
    # -------------------------------------------------------------------------
    def test_25_deduplication_cache_prevents_unnecessary_repeat_analysis(self):
        """Verifies identical comment text is cached and does not trigger duplicate model invocations."""
        sentiment_service.clear_sentiment_cache()

        class CountingProvider:
            def __init__(self):
                self.calls = 0
            def get_provider_name(self):
                return "counting_mock"
            async def analyze_sentiment(self, text, language="en"):
                self.calls += 1
                from app.services.ai.base import SentimentAnalysisResult
                return SentimentAnalysisResult(
                    sentiment="Positive",
                    score=0.85,
                    confidence=0.92,
                    method="model:counting_mock",
                )

        provider = CountingProvider()
        test_text = "Unique citizen response for caching verification"

        # First call: hits provider
        res1 = asyncio.run(sentiment_service.analyze_sentiment_model(test_text, provider=provider))
        self.assertEqual(provider.calls, 1)
        self.assertEqual(res1.sentiment, "Positive")

        # Second call with identical text: hits cache, provider NOT called again
        res2 = asyncio.run(sentiment_service.analyze_sentiment_model(test_text, provider=provider))
        self.assertEqual(provider.calls, 1)  # Call count remains 1!
        self.assertEqual(res2.sentiment, "Positive")
        self.assertEqual(res2.score, res1.score)

        # Clear cache and call again: provider is called
        sentiment_service.clear_sentiment_cache()
        res3 = asyncio.run(sentiment_service.analyze_sentiment_model(test_text, provider=provider))
        self.assertEqual(provider.calls, 2)
        self.assertEqual(res3.sentiment, "Positive")
