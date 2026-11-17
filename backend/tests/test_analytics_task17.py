"""Automated Unit and Integration Tests for Milestone 3, Task 17:
Analytics Dashboards & Reporting.

Covers:
1. Dashboard KPI calculations (open rate, CTR, reach, response rate, status counts)
2. Engagement trends time-series aggregation (daily, weekly, monthly)
3. Channel-wise breakdown (Email, SMS, WhatsApp, Push, Web Broadcast)
4. Language-wise breakdown and sentiment distribution
5. Audience-segment performance aggregation
6. Best and worst campaign rankings
7. Campaign conversion funnel (Sent -> Delivered -> Opened -> Clicked -> Responded)
8. Date-range filtering (start_date, end_date)
9. Channel, language, and segment filters
10. Empty database and zero-denominator safety (no ZeroDivisionError)
11. CSV export content, metadata, and attachment headers
12. PDF export byte stream (%PDF-1.4, application/pdf)
13. AI / rules-based actionable insight generation
14. Fallback behavior when AI provider is unavailable
15. Authentication and Role-Based Access Control (401, 403, 200)
16. Invalid date range validation (400 when start > end)
17. Single-campaign comprehensive report endpoint (200 OK and 404 Not Found)
"""

import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone, timedelta, date

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
from app.models.segment import Segment, campaign_segments
from app.models.communication import Message, Feedback
from app.models.engagement import TrackedLink, EngagementEvent


def seed_roles(db):
    roles = [
        Role(id=1, name="Admin", description="Administrator"),
        Role(id=2, name="Campaign Manager", description="Campaign Manager"),
        Role(id=3, name="Communication Team", description="Communication Team"),
        Role(id=4, name="Viewer", description="Read-only Citizen / External"),
    ]
    for r in roles:
        if not db.get(Role, r.id):
            db.add(r)
    db.commit()


class TestAnalyticsTask17(unittest.TestCase):
    """Full unit and integration test suite for Milestone 3, Task 17."""

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

        # Seed roles
        seed_roles(self.db)

        # Users
        self.admin_user = User(
            id=1,
            full_name="Admin Director",
            email="admin@masscomm.gov.in",
            hashed_password=get_password_hash("AdminPass123!"),
            role_id=1,
            is_active=True,
        )
        self.manager_user = User(
            id=2,
            full_name="Campaign Manager",
            email="manager@masscomm.gov.in",
            hashed_password=get_password_hash("ManagerPass123!"),
            role_id=2,
            is_active=True,
        )
        self.comm_user = User(
            id=3,
            full_name="Comm Officer",
            email="comm@masscomm.gov.in",
            hashed_password=get_password_hash("CommPass123!"),
            role_id=3,
            is_active=True,
        )
        self.viewer_user = User(
            id=4,
            full_name="Unauthorized Viewer",
            email="viewer@external.gov.in",
            hashed_password=get_password_hash("ViewerPass123!"),
            role_id=4,
            is_active=True,
        )
        self.db.add_all([self.admin_user, self.manager_user, self.comm_user, self.viewer_user])
        self.db.commit()

        # Auth headers
        self.admin_token = create_access_token(self.admin_user.id)
        self.admin_headers = {"Authorization": f"Bearer {self.admin_token}"}

        self.manager_token = create_access_token(self.manager_user.id)
        self.manager_headers = {"Authorization": f"Bearer {self.manager_token}"}

        self.comm_token = create_access_token(self.comm_user.id)
        self.comm_headers = {"Authorization": f"Bearer {self.comm_token}"}

        self.viewer_token = create_access_token(self.viewer_user.id)
        self.viewer_headers = {"Authorization": f"Bearer {self.viewer_token}"}

    def tearDown(self):
        self.db.close()
        app.dependency_overrides.clear()

    def _seed_sample_analytics_dataset(self):
        """Populates rich dataset with campaigns, messages, links, events, and feedback."""
        now = datetime.now(timezone.utc)
        yesterday = now - timedelta(days=1)
        two_days_ago = now - timedelta(days=2)

        # Campaigns
        c1 = Campaign(
            id=101,
            name="Flood Relief Alert 2026",
            campaign_type="Emergency Alert",
            objective="Emergency safety bulletin",
            status="completed",
            channels=["SMS", "WhatsApp", "Email"],
            created_by=1,
            created_at=two_days_ago,
        )
        c2 = Campaign(
            id=102,
            name="Digital India Portal Awareness",
            campaign_type="Awareness",
            objective="Public welfare literacy",
            status="active",
            channels=["Push", "Web Broadcast"],
            created_by=2,
            created_at=yesterday,
        )
        self.db.add_all([c1, c2])

        # Segments
        s1 = Segment(
            id=201,
            name="Rural Farmers",
            description="Rural agricultural community",
            created_by=1,
        )
        s2 = Segment(
            id=202,
            name="Urban Youth",
            description="College students and urban youth",
            created_by=1,
        )
        self.db.add_all([s1, s2])
        self.db.commit()

        # Link campaigns to segments
        self.db.execute(
            campaign_segments.insert().values(
                [
                    {"campaign_id": 101, "segment_id": 201},
                    {"campaign_id": 102, "segment_id": 202},
                ]
            )
        )

        # Audience Members
        a1 = AudienceMember(id=301, name="Citizen One", email="c1@example.com", phone="+919000000001", consent_status=True)
        a2 = AudienceMember(id=302, name="Citizen Two", email="c2@example.com", phone="+919000000002", consent_status=True)
        a3 = AudienceMember(id=303, name="Citizen Three", email="c3@example.com", phone="+919000000003", consent_status=True)
        a4 = AudienceMember(id=304, name="Citizen Four", email="c4@example.com", phone="+919000000004", consent_status=True)
        self.db.add_all([a1, a2, a3, a4])
        self.db.commit()

        # Messages
        # Campaign 101: 4 messages (3 delivered, 1 failed)
        m1 = Message(
            id=1,
            campaign_id=101,
            audience_member_id=301,
            channel="SMS",
            language="hi",
            rendered_content="बाढ़ राहत शिविर की जानकारी",
            status="Delivered",
            tracking_id="trk-sms-1",
            created_at=two_days_ago,
            sent_at=two_days_ago,
            delivered_at=two_days_ago,
        )
        m2 = Message(
            id=2,
            campaign_id=101,
            audience_member_id=302,
            channel="WhatsApp",
            language="en",
            rendered_content="Flood relief alert details and link",
            status="Delivered",
            tracking_id="trk-wa-2",
            created_at=yesterday,
            sent_at=yesterday,
            delivered_at=yesterday,
        )
        m3 = Message(
            id=3,
            campaign_id=101,
            audience_member_id=303,
            channel="Email",
            language="hi",
            rendered_content="सुरक्षा निर्देश और हेल्पलाइन नंबर",
            status="Delivered",
            tracking_id="trk-em-3",
            created_at=now,
            sent_at=now,
            delivered_at=now,
        )
        m4 = Message(
            id=4,
            campaign_id=101,
            audience_member_id=304,
            channel="SMS",
            language="hi",
            rendered_content="एसएमएस डिलीवरी परीक्षण",
            status="Failed",
            tracking_id="trk-sms-4",
            created_at=now,
            sent_at=now,
        )

        # Campaign 102: 2 messages (2 delivered)
        m5 = Message(
            id=5,
            campaign_id=102,
            audience_member_id=301,
            channel="Push",
            language="ta",
            rendered_content="டிஜிட்டல் இந்தியா விழிப்புணர்வு",
            status="Delivered",
            tracking_id="trk-push-5",
            created_at=yesterday,
            sent_at=yesterday,
            delivered_at=yesterday,
        )
        m6 = Message(
            id=6,
            campaign_id=102,
            audience_member_id=302,
            channel="Web Broadcast",
            language="en",
            rendered_content="Digital portal citizen services",
            status="Delivered",
            tracking_id="trk-wb-6",
            created_at=now,
            sent_at=now,
            delivered_at=now,
        )
        self.db.add_all([m1, m2, m3, m4, m5, m6])
        self.db.commit()

        # Tracked Links
        l1 = TrackedLink(
            id=10,
            link_id="shltr1",
            campaign_id=101,
            message_id=2,
            original_url="https://relief.gov.in/shelter",
        )
        self.db.add(l1)
        self.db.commit()

        # Engagement Events
        e1 = EngagementEvent(
            id=1,
            campaign_id=101,
            message_id=2,
            event_type="open",
            language="en",
            timestamp=yesterday,
        )
        e2 = EngagementEvent(
            id=2,
            campaign_id=101,
            message_id=3,
            event_type="open",
            language="hi",
            timestamp=now,
        )
        e3 = EngagementEvent(
            id=3,
            campaign_id=101,
            message_id=2,
            event_type="click",
            link_url="https://relief.gov.in/shelter",
            language="en",
            timestamp=yesterday,
        )
        e4 = EngagementEvent(
            id=4,
            campaign_id=101,
            message_id=1,
            event_type="reply",
            language="hi",
            timestamp=yesterday,
        )
        self.db.add_all([e1, e2, e3, e4])

        # Feedback
        fb1 = Feedback(
            id=1,
            campaign_id=101,
            audience_member_id=301,
            message_id=1,
            rating=5,
            comment="Very clear and life saving alert, thank you!",
            language="hi",
            sentiment_label="Positive",
            sentiment_score=0.92,
            created_at=yesterday,
        )
        fb2 = Feedback(
            id=2,
            campaign_id=101,
            audience_member_id=302,
            message_id=2,
            rating=2,
            comment="The shelter location details were confusing.",
            language="en",
            sentiment_label="Negative",
            sentiment_score=-0.65,
            created_at=yesterday,
        )
        self.db.add_all([fb1, fb2])
        self.db.commit()

    def test_01_global_kpis_calculation(self):
        """Verifies accurate KPI mathematical calculations against seeded records."""
        self._seed_sample_analytics_dataset()

        resp = self.client.get("/analytics/kpis", headers=self.admin_headers)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        # 2 campaigns
        self.assertEqual(data["total_campaigns"], 2)
        # 6 messages sent
        self.assertEqual(data["total_messages_sent"], 6)
        # 5 delivered (m1, m2, m3, m5, m6)
        self.assertEqual(data["total_delivered"], 5)
        # 3 unique citizens reached (301, 302, 303; 304 failed)
        self.assertEqual(data["total_reach"], 3)
        # Delivery rate = 5 / 6 * 100 = 83.33%
        self.assertAlmostEqual(data["delivery_rate"], 83.33, places=2)
        # Bounce rate = 1 / 6 * 100 = 16.67%
        self.assertAlmostEqual(data["bounce_rate"], 16.67, places=2)
        # Status counts
        self.assertEqual(data["status_counts"]["delivered"], 5)
        self.assertEqual(data["status_counts"]["failed"], 1)
        # Opens: 2 unique messages opened (m2, m3) / 5 delivered = 40.0%
        self.assertAlmostEqual(data["average_open_rate"], 40.0, places=2)
        # Clicks: 1 unique clicked / 5 delivered = 20.0%
        self.assertAlmostEqual(data["average_click_through_rate"], 20.0, places=2)
        # Replies: 1 replied / 5 delivered = 20.0%
        self.assertAlmostEqual(data["response_rate"], 20.0, places=2)
        # Participation rate: 2 feedback / 5 delivered = 40.0%
        self.assertAlmostEqual(data["participation_rate"], 40.0, places=2)

    def test_02_engagement_trends_time_series(self):
        """Verifies engagement trends time series aggregation."""
        self._seed_sample_analytics_dataset()

        resp = self.client.get("/analytics/trends?interval=daily", headers=self.admin_headers)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        self.assertIn("trends", data)
        self.assertGreaterEqual(len(data["trends"]), 1)

        # Check fields of data point
        point = data["trends"][-1]
        for key in ["date", "sent", "delivered", "opens", "clicks", "replies", "participations"]:
            self.assertIn(key, point)

        # Test weekly and monthly intervals
        weekly_resp = self.client.get("/analytics/trends?interval=weekly", headers=self.admin_headers)
        self.assertEqual(weekly_resp.status_code, 200)
        self.assertEqual(weekly_resp.json()["interval"], "weekly")

        monthly_resp = self.client.get("/analytics/trends?interval=monthly", headers=self.admin_headers)
        self.assertEqual(monthly_resp.status_code, 200)
        self.assertEqual(monthly_resp.json()["interval"], "monthly")

    def test_03_channel_performance_breakdown(self):
        """Verifies channel-wise breakdown for all 5 core channels."""
        self._seed_sample_analytics_dataset()

        resp = self.client.get("/analytics/breakdowns", headers=self.admin_headers)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        by_ch = data["by_channel"]
        for ch in ["SMS", "WhatsApp", "Email", "Push", "Web Broadcast"]:
            self.assertIn(ch, by_ch)
            self.assertIn("delivery_rate", by_ch[ch])
            self.assertIn("open_rate", by_ch[ch])
            self.assertIn("ctr", by_ch[ch])

        # SMS: 2 sent, 1 delivered, 1 failed -> 50% delivery rate
        self.assertEqual(by_ch["SMS"]["sent"], 2)
        self.assertEqual(by_ch["SMS"]["delivered"], 1)
        self.assertEqual(by_ch["SMS"]["failed"], 1)
        self.assertEqual(by_ch["SMS"]["delivery_rate"], 50.0)

        # WhatsApp: 1 sent, 1 delivered, 1 opened, 1 clicked
        self.assertEqual(by_ch["WhatsApp"]["sent"], 1)
        self.assertEqual(by_ch["WhatsApp"]["delivered"], 1)
        self.assertEqual(by_ch["WhatsApp"]["opens"], 1)
        self.assertEqual(by_ch["WhatsApp"]["open_rate"], 100.0)
        self.assertEqual(by_ch["WhatsApp"]["clicks"], 1)
        self.assertEqual(by_ch["WhatsApp"]["ctr"], 100.0)

    def test_04_language_breakdown_and_sentiment(self):
        """Verifies language-wise breakdown and sentiment distribution."""
        self._seed_sample_analytics_dataset()

        resp = self.client.get("/analytics/breakdowns", headers=self.admin_headers)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        by_lang = data["by_language"]
        self.assertIn("hi", by_lang)
        self.assertIn("en", by_lang)

        # Hindi: 3 messages (2 delivered, 1 open, 1 reply)
        self.assertEqual(by_lang["hi"]["messages"], 3)
        self.assertEqual(by_lang["hi"]["delivered"], 2)
        self.assertIn("sentiment_distribution", by_lang["hi"])
        self.assertEqual(by_lang["hi"]["sentiment_distribution"]["Positive"], 1)

        # English: 1 negative feedback
        self.assertEqual(by_lang["en"]["sentiment_distribution"]["Negative"], 1)

    def test_05_audience_segment_breakdown(self):
        """Verifies audience segment breakdown correctly aggregates metrics."""
        self._seed_sample_analytics_dataset()

        resp = self.client.get("/analytics/breakdowns", headers=self.admin_headers)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        by_seg = data["by_segment"]
        self.assertGreaterEqual(len(by_seg), 2)
        seg_names = [s["segment_name"] for s in by_seg]
        self.assertIn("Rural Farmers", seg_names)
        self.assertIn("Urban Youth", seg_names)

    def test_06_best_and_worst_campaign_rankings(self):
        """Verifies campaign ranking into best and worst performers."""
        self._seed_sample_analytics_dataset()

        resp = self.client.get("/analytics/breakdowns", headers=self.admin_headers)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        self.assertIn("best_performing", data)
        self.assertIn("worst_performing", data)
        self.assertGreaterEqual(len(data["best_performing"]), 1)
        for c in data["best_performing"]:
            self.assertIn("engagement_score", c)
            self.assertIn("campaign_name", c)

    def test_07_campaign_funnel_stages(self):
        """Verifies 5-stage conversion funnel and step dropoff calculations."""
        self._seed_sample_analytics_dataset()

        resp = self.client.get("/analytics/funnel", headers=self.admin_headers)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        self.assertEqual(len(data["stages"]), 5)
        stage_names = [s["stage"] for s in data["stages"]]
        self.assertEqual(stage_names, ["Sent", "Delivered", "Opened", "Clicked", "Responded"])

        sent_stage = data["stages"][0]
        self.assertEqual(sent_stage["count"], 6)
        self.assertEqual(sent_stage["conversion_from_top"], 100.0)

        delivered_stage = data["stages"][1]
        self.assertEqual(delivered_stage["count"], 5)
        self.assertAlmostEqual(delivered_stage["conversion_from_top"], 83.33, places=2)

        self.assertIn("overall_conversion_rate", data)

    def test_08_date_range_filtering(self):
        """Verifies date range query filters accurately exclude out-of-range records."""
        self._seed_sample_analytics_dataset()

        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        resp = self.client.get(
            f"/analytics/kpis?start_date={today_str}&end_date={today_str}",
            headers=self.admin_headers,
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        # Today had m3 (hi), m4 (hi), m6 (en)
        self.assertEqual(data["total_messages_sent"], 3)

    def test_09_channel_language_and_segment_filters(self):
        """Verifies channel, language, and segment filtering isolate expected records."""
        self._seed_sample_analytics_dataset()

        # Channel filter
        resp_sms = self.client.get("/analytics/kpis?channel=SMS", headers=self.admin_headers)
        self.assertEqual(resp_sms.status_code, 200)
        self.assertEqual(resp_sms.json()["total_messages_sent"], 2)

        # Language filter
        resp_ta = self.client.get("/analytics/kpis?language=ta", headers=self.admin_headers)
        self.assertEqual(resp_ta.status_code, 200)
        self.assertEqual(resp_ta.json()["total_messages_sent"], 1)

        # Segment filter
        resp_seg = self.client.get("/analytics/kpis?segment_id=202", headers=self.admin_headers)
        self.assertEqual(resp_seg.status_code, 200)
        self.assertEqual(resp_seg.json()["total_messages_sent"], 2)

    def test_10_empty_database_and_zero_denominator_safety(self):
        """Verifies zero-division protection when no records exist."""
        # Empty database (no seed)
        endpoints = [
            "/analytics/kpis",
            "/analytics/trends",
            "/analytics/breakdowns",
            "/analytics/funnel",
            "/analytics/insights",
        ]
        for ep in endpoints:
            resp = self.client.get(ep, headers=self.admin_headers)
            self.assertEqual(resp.status_code, 200, f"Endpoint {ep} failed on empty database")

        kpi_data = self.client.get("/analytics/kpis", headers=self.admin_headers).json()
        self.assertEqual(kpi_data["total_messages_sent"], 0)
        self.assertEqual(kpi_data["delivery_rate"], 0.0)
        self.assertEqual(kpi_data["average_open_rate"], 0.0)
        self.assertEqual(kpi_data["average_click_through_rate"], 0.0)
        self.assertEqual(kpi_data["response_rate"], 0.0)
        self.assertEqual(kpi_data["participation_rate"], 0.0)

    def test_11_csv_export_format_and_content(self):
        """Verifies structured CSV export output and proper HTTP headers."""
        self._seed_sample_analytics_dataset()

        resp = self.client.get("/analytics/export/csv", headers=self.admin_headers)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("text/csv", resp.headers.get("content-type", ""))
        self.assertIn("attachment; filename=", resp.headers.get("content-disposition", ""))

        text = resp.text
        self.assertIn("MASSCOMMAI EXECUTIVE ANALYTICS REPORT", text)
        self.assertIn("KEY PERFORMANCE INDICATORS", text)
        self.assertIn("CAMPAIGN CONVERSION FUNNEL", text)
        self.assertIn("CHANNEL PERFORMANCE BREAKDOWN", text)
        self.assertIn("LANGUAGE ENGAGEMENT BREAKDOWN", text)
        self.assertIn("Total Messages Sent", text)

    def test_12_pdf_export_binary_stream(self):
        """Verifies PDF binary stream output with valid PDF structure."""
        self._seed_sample_analytics_dataset()

        resp = self.client.get("/analytics/export/pdf", headers=self.admin_headers)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.headers.get("content-type"), "application/pdf")
        self.assertIn("attachment; filename=", resp.headers.get("content-disposition", ""))

        content = resp.content
        self.assertTrue(content.startswith(b"%PDF-1.4"), "PDF must begin with %PDF-1.4 header")
        self.assertTrue(content.endswith(b"%%EOF\n") or b"%%EOF" in content, "PDF must end with %%EOF")

    def test_13_ai_rules_insights_generation(self):
        """Verifies generation of plain-English actionable insights with evidence."""
        self._seed_sample_analytics_dataset()

        resp = self.client.get("/analytics/insights", headers=self.admin_headers)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        self.assertIn("insights", data)
        self.assertIn("generated_at", data)
        self.assertGreaterEqual(len(data["insights"]), 1)

        first = data["insights"][0]
        self.assertIn("title", first)
        self.assertIn("description", first)
        self.assertIn("evidence", first)
        self.assertIn("recommendation", first)
        self.assertIn("severity", first)

    def test_14_ai_provider_fallback_behavior(self):
        """Verifies deterministic fallback rules generate valid insights if AI provider fails."""
        self._seed_sample_analytics_dataset()

        with patch("app.services.analytics_service.get_ai_provider", side_effect=RuntimeError("AI offline")):
            resp = self.client.get("/analytics/insights", headers=self.admin_headers)
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertGreaterEqual(len(data["insights"]), 1)
            self.assertEqual(data["generation_method"], "rules_engine_fallback")

    def test_15_authentication_and_rbac(self):
        """Verifies RBAC protection: 401 unauthenticated, 403 unauthorized, 200 authorized."""
        # Unauthenticated request -> 401
        unauth_resp = self.client.get("/analytics/kpis")
        self.assertEqual(unauth_resp.status_code, 401)

        # Unauthorized viewer role (id=4) -> 403
        viewer_resp = self.client.get("/analytics/kpis", headers=self.viewer_headers)
        self.assertEqual(viewer_resp.status_code, 403)

        # Authorized Admin -> 200
        admin_resp = self.client.get("/analytics/kpis", headers=self.admin_headers)
        self.assertEqual(admin_resp.status_code, 200)

        # Authorized Campaign Manager -> 200
        mgr_resp = self.client.get("/analytics/kpis", headers=self.manager_headers)
        self.assertEqual(mgr_resp.status_code, 200)

        # Authorized Communication Team -> 200
        comm_resp = self.client.get("/analytics/kpis", headers=self.comm_headers)
        self.assertEqual(comm_resp.status_code, 200)

    def test_16_invalid_date_range_validation(self):
        """Verifies validation rejecting start_date > end_date and malformed date strings."""
        # start_date > end_date -> 400
        resp = self.client.get(
            "/analytics/kpis?start_date=2026-12-31&end_date=2026-01-01",
            headers=self.admin_headers,
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("start_date must be before or equal to end_date", resp.json()["detail"])

        # Malformed date string -> 400
        bad_format_resp = self.client.get(
            "/analytics/kpis?start_date=invalid-date",
            headers=self.admin_headers,
        )
        self.assertEqual(bad_format_resp.status_code, 400)
        self.assertIn("Invalid date format", bad_format_resp.json()["detail"])

    def test_17_campaign_specific_report(self):
        """Verifies single-campaign comprehensive dossier and 404 handling."""
        self._seed_sample_analytics_dataset()

        # Existing campaign -> 200 OK
        resp = self.client.get("/analytics/campaign-report/101", headers=self.admin_headers)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["campaign_id"], 101)
        self.assertEqual(data["campaign_name"], "Flood Relief Alert 2026")
        self.assertIn("kpis", data)
        self.assertIn("funnel", data)
        self.assertIn("sentiment_summary", data)
        self.assertEqual(data["sentiment_summary"]["total_feedback"], 2)

        # Nonexistent campaign -> 404 Not Found
        not_found_resp = self.client.get("/analytics/campaign-report/99999", headers=self.admin_headers)
        self.assertEqual(not_found_resp.status_code, 404)


if __name__ == "__main__":
    unittest.main()
