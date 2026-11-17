"""Comprehensive End-to-End Workflow Integration Test for MassCommAI (Task 18).

Validates the full institutional lifecycle in sequential order:
1. User Registration (Public self-registration -> Communication Team role)
2. Authentication (Login -> JWT Bearer access token issue)
3. Audience Ingestion & Management (Create recipient with language & consent)
4. Dynamic Demographic Segmentation (Define AST rule criteria)
5. Campaign Composition (Configure channels, metadata, and link segment)
6. AI Content Generation (Studio prompt synthesis with mock provider fallback)
7. Editorial Review & Content Approval (Review lifecycle -> Approved)
8. Campaign Governance & Administrative Approval (Status -> Approved)
9. Campaign Dispatch Execution (Multi-channel broadcast distribution)
10. Delivery Status & Tracking Verification (Tracking IDs, messages, logs)
11. Public Engagement & Feedback (Click tracking link & submit citizen feedback)
12. Performance Analytics & KPIs (Dashboard aggregation & reporting)
"""

import unittest
from datetime import datetime, timezone, timedelta
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.main import app
from app.db.base import Base
from app.db.session import get_db
from app.db.seed import seed_default_roles
from app.models.user import User, Role
from app.models.channel_config import ChannelConfiguration
from app.core.security import get_password_hash, create_access_token
from app.core.rate_limiter import reset_rate_limiters


class TestEndToEndWorkflow(unittest.TestCase):
    """End-to-end user journey test suite."""

    @classmethod
    def setUpClass(cls):
        cls.test_engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        cls.TestingSessionLocal = sessionmaker(
            autocommit=False, autoflush=False, bind=cls.test_engine
        )

    def setUp(self):
        reset_rate_limiters()
        Base.metadata.create_all(bind=self.test_engine)
        self.db = self.TestingSessionLocal()
        roles = seed_default_roles(self.db)
        self.admin_role = roles["Admin"]
        self.manager_role = roles["Campaign Manager"]
        self.comm_role = roles["Communication Team"]

        # Bootstrap an administrative campaign manager for approvals
        self.manager_user = User(
            full_name="Campaign Manager Admin",
            email="manager.e2e@gov.in",
            hashed_password=get_password_hash("ManagerPass123!"),
            role_id=self.manager_role.id,
            is_active=True,
        )
        self.db.add(self.manager_user)

        # Seed enabled mock channel configurations
        channels = ["SMS", "Email", "WhatsApp"]
        for ch in channels:
            cfg = ChannelConfiguration(
                channel=ch,
                is_enabled=True,
                provider_type="mock",
                sender_address="GOVALERT",
                sender_name="Government Alert System",
                credentials={},
            )
            self.db.add(cfg)

        self.db.commit()
        self.db.refresh(self.manager_user)
        self.manager_token = create_access_token(subject=self.manager_user.id)
        self.manager_headers = {"Authorization": f"Bearer {self.manager_token}"}

        def override_get_db():
            try:
                yield self.db
            finally:
                pass

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()
        self.db.close()
        Base.metadata.drop_all(bind=self.test_engine)
        reset_rate_limiters()

    def test_complete_platform_lifecycle_e2e(self):
        """Executes the full 12-step institutional workflow sequentially."""

        # -------------------------------------------------------------
        # STEP 1: User Self-Registration
        # -------------------------------------------------------------
        reg_payload = {
            "full_name": "Arjun Singhal",
            "email": "arjun.singhal@gov.in",
            "password": "StrongPassword999!",
            "phone": "+919876543219",
            "organization": "National Disaster Response Force",
        }
        reg_resp = self.client.post("/auth/register", json=reg_payload)
        self.assertEqual(reg_resp.status_code, 201, f"Register failed: {reg_resp.text}")
        reg_data = reg_resp.json()
        self.assertEqual(reg_data["status"], "success")
        registered_user_id = reg_data["user"]["id"]
        # Default registration role must be Communication Team
        self.assertEqual(reg_data["user"]["role_name"], "Communication Team")

        # -------------------------------------------------------------
        # STEP 2: User Authentication & JWT Token Issuance
        # -------------------------------------------------------------
        login_payload = {
            "email": "arjun.singhal@gov.in",
            "password": "StrongPassword999!",
        }
        login_resp = self.client.post("/auth/login", json=login_payload)
        self.assertEqual(login_resp.status_code, 200, f"Login failed: {login_resp.text}")
        login_data = login_resp.json()
        auth_token = login_data["access_token"]
        self.assertTrue(auth_token.startswith("eyJ"))
        auth_headers = {"Authorization": f"Bearer {auth_token}"}

        # Verify /auth/me profile retrieval
        me_resp = self.client.get("/auth/me", headers=auth_headers)
        self.assertEqual(me_resp.status_code, 200)
        self.assertEqual(me_resp.json()["email"], "arjun.singhal@gov.in")

        # -------------------------------------------------------------
        # STEP 3: Audience Management (Citizen Ingestion & RBAC)
        # -------------------------------------------------------------
        # 3a. Communication Team can read audience
        read_resp = self.client.get("/audience", headers=auth_headers)
        self.assertEqual(read_resp.status_code, 200)

        # 3b. Audience ingestion requires Campaign Manager / Admin
        citizen_payload = {
            "name": "Ramesh Chandra",
            "email": "ramesh.chandra@citizen.gov.in",
            "phone": "+919822334455",
            "age": 45,
            "gender": "Male",
            "city": "Lucknow",
            "state": "Uttar Pradesh",
            "preferred_language": "hi",
            "occupation": "Farmer",
            "organization_department": "Krishi Samiti",
            "preferred_channel": "SMS",
            "consent_status": True,
        }
        citizen_resp = self.client.post("/audience/", headers=self.manager_headers, json=citizen_payload)
        self.assertEqual(citizen_resp.status_code, 201, f"Audience creation failed: {citizen_resp.text}")
        citizen_id = citizen_resp.json()["id"]
        self.assertEqual(citizen_resp.json()["name"], "Ramesh Chandra")

        # -------------------------------------------------------------
        # STEP 4: Audience Segmentation
        # -------------------------------------------------------------
        segment_payload = {
            "name": "UP Agrarian Citizens",
            "description": "Farmers and agrarian residents of Uttar Pradesh",
            "filter_rules": {
                "connector": "AND",
                "conditions": [
                    {"field": "state", "operator": "equals", "value": "Uttar Pradesh"},
                    {"field": "occupation", "operator": "equals", "value": "Farmer"},
                ],
            },
        }
        segment_resp = self.client.post("/segments/", headers=self.manager_headers, json=segment_payload)
        self.assertEqual(segment_resp.status_code, 201, f"Segment creation failed: {segment_resp.text}")
        segment_id = segment_resp.json()["id"]

        # -------------------------------------------------------------
        # STEP 5: Template & Campaign Creation
        # -------------------------------------------------------------
        tmpl_payload = {
            "title": "E2E Monsoon Flood Advisory Template",
            "category": "Emergency Alert",
            "language": "en",
            "body": "Dear {name}, urgent flash flood advisory for {city}, {state}. Helpline: 1077.",
            "tags": "emergency,flood,monsoon",
        }
        tmpl_resp = self.client.post("/templates/", headers=self.manager_headers, json=tmpl_payload)
        self.assertEqual(tmpl_resp.status_code, 201, f"Template creation failed: {tmpl_resp.text}")
        tmpl_id = tmpl_resp.json()["id"]

        now = datetime.now(timezone.utc)
        campaign_payload = {
            "name": "E2E Monsoon Alert Drive",
            "campaign_type": "Emergency Alert",
            "objective": "Urgent weather advisory and flood precaution notices for agrarian sectors.",
            "priority": "High",
            "channels": ["SMS", "Email"],
            "template_id": tmpl_id,
            "start_date": (now - timedelta(hours=1)).isoformat(),
            "end_date": (now + timedelta(days=3)).isoformat(),
            "segment_ids": [segment_id],
        }
        campaign_resp = self.client.post("/campaigns/", headers=self.manager_headers, json=campaign_payload)
        self.assertEqual(campaign_resp.status_code, 201, f"Campaign creation failed: {campaign_resp.text}")
        campaign_id = campaign_resp.json()["id"]
        self.assertEqual(campaign_resp.json()["status"], "Draft")

        # -------------------------------------------------------------
        # STEP 6: AI Content Generation in Studio
        # -------------------------------------------------------------
        content_brief = {
            "topic": "Urgent Monsoon Flash Flood Warning",
            "category": "Disaster Preparedness",
            "objective": "Advise farmers to move cattle to higher ground and secure equipment.",
            "channel": "SMS",
            "tone": "urgent",
            "target_language": "en",
            "facts": "Heavy rainfall expected in Lucknow. Emergency helpline 1077 active.",
        }
        content_resp = self.client.post("/content/generate", headers=self.manager_headers, json=content_brief)
        self.assertEqual(content_resp.status_code, 201, f"AI generation failed: {content_resp.text}")
        content_asset = content_resp.json()
        asset_id = content_asset["id"]
        self.assertEqual(content_asset["review_status"], "Draft")

        # Attach content asset to campaign
        attach_resp = self.client.post(
            f"/content/{asset_id}/attach",
            headers=self.manager_headers,
            json={"campaign_id": campaign_id},
        )
        self.assertEqual(attach_resp.status_code, 200, f"Attach content failed: {attach_resp.text}")

        # -------------------------------------------------------------
        # STEP 7: Quality Assessment & Editorial Content Approval
        # -------------------------------------------------------------
        # 7a. Trigger quality and compliance assessment
        eval_resp = self.client.post(f"/content/{asset_id}/evaluate", headers=self.manager_headers)
        self.assertEqual(eval_resp.status_code, 200, f"Quality evaluation failed: {eval_resp.text}")

        # 7b. Transition review status to Approved
        review_resp = self.client.patch(
            f"/content/{asset_id}/review",
            headers=self.manager_headers,
            json={"review_status": "Approved", "review_notes": "Emergency factual content validated."},
        )
        self.assertEqual(review_resp.status_code, 200, f"Content approval failed: {review_resp.text}")
        self.assertEqual(review_resp.json()["review_status"], "Approved")

        # -------------------------------------------------------------
        # STEP 8: Administrative Campaign Approval
        # -------------------------------------------------------------
        camp_approve_resp = self.client.patch(
            f"/campaigns/{campaign_id}/status",
            headers=self.manager_headers,
            json={"status": "Approved"},
        )
        self.assertEqual(camp_approve_resp.status_code, 200, f"Campaign approval failed: {camp_approve_resp.text}")
        self.assertEqual(camp_approve_resp.json()["status"], "Approved")

        # -------------------------------------------------------------
        # STEP 9: Campaign Broadcast Dispatch
        # -------------------------------------------------------------
        send_resp = self.client.post(
            f"/campaigns/{campaign_id}/send",
            headers=self.manager_headers,
            json={"channels": ["SMS"]},
        )
        self.assertEqual(send_resp.status_code, 200, f"Campaign send failed: {send_resp.text}")
        send_data = send_resp.json()
        self.assertEqual(send_data["delivered_messages"], 1, "1 message should be delivered")
        self.assertEqual(send_data["failed_messages"], 0)
        self.assertEqual(send_data["campaign_status"], "Completed")

        # -------------------------------------------------------------
        # STEP 10: Delivery Tracking & Message Audit Verification
        # -------------------------------------------------------------
        messages_list = send_data["messages"]
        self.assertEqual(len(messages_list), 1)

        dispatched_msg = messages_list[0]
        tracking_id = dispatched_msg["tracking_id"]
        self.assertTrue(tracking_id.startswith("trk_"))
        self.assertEqual(dispatched_msg["status"], "Delivered")

        # Fetch message record from DB to verify feedback token
        from app.models.communication import Message
        db_msg = self.db.execute(select(Message).where(Message.campaign_id == campaign_id)).scalar_one_or_none()
        self.assertIsNotNone(db_msg)
        feedback_token = db_msg.feedback_token
        self.assertTrue(feedback_token.startswith("fbt_"))

        # -------------------------------------------------------------
        # STEP 11: Public Engagement & Citizen Feedback
        # -------------------------------------------------------------
        # 11a: Public feedback info metadata without PII
        fb_info_resp = self.client.get(f"/feedback/info/{feedback_token}")
        self.assertEqual(fb_info_resp.status_code, 200)
        fb_info = fb_info_resp.json()
        self.assertEqual(fb_info["campaign_name"], "E2E Monsoon Alert Drive")
        self.assertEqual(fb_info["feedback_token"], feedback_token)

        # 11b: Citizen feedback submission with sentiment analysis
        fb_submit_resp = self.client.post(
            "/feedback/submit",
            json={
                "feedback_token": feedback_token,
                "rating": 5,
                "comment": "Great service and excellent emergency advisory! Very helpful.",
            },
        )
        self.assertEqual(fb_submit_resp.status_code, 201, f"Feedback submission failed: {fb_submit_resp.text}")
        fb_result = fb_submit_resp.json()
        self.assertEqual(fb_result["sentiment_label"], "Positive")
        self.assertGreater(fb_result["sentiment_score"], 0.0)

        # -------------------------------------------------------------
        # STEP 12: Campaign Analytics & Reporting
        # -------------------------------------------------------------
        kpi_resp = self.client.get(f"/analytics/kpis?campaign_id={campaign_id}", headers=self.manager_headers)
        self.assertEqual(kpi_resp.status_code, 200, f"Analytics KPIs failed: {kpi_resp.text}")
        kpis = kpi_resp.json()
        self.assertGreaterEqual(kpis["total_messages_sent"], 1)
        self.assertGreaterEqual(kpis["total_delivered"], 1)
        self.assertEqual(kpis["bounce_rate"], 0.0)
        self.assertGreaterEqual(kpis["delivery_rate"], 100.0)

        # Verify campaign report endpoint
        report_resp = self.client.get(f"/analytics/campaign-report/{campaign_id}", headers=self.manager_headers)
        self.assertEqual(report_resp.status_code, 200, f"Campaign report failed: {report_resp.text}")
        report = report_resp.json()
        self.assertEqual(report["campaign_id"], campaign_id)
        self.assertEqual(report["campaign_name"], "E2E Monsoon Alert Drive")
        self.assertIn("kpis", report)
        self.assertIn("funnel", report)
        self.assertIn("sentiment_summary", report)
