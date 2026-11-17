"""Automated Unit and Integration Tests for Milestone 3, Task 15:
Scheduling, Automated Workflows & Delivery Tracking with Retry.

Covers:
1. Immediate campaign execution (schedule_type='now')
2. Future campaign scheduling (schedule_type='once')
3. Daily recurring campaigns
4. Weekly recurring campaigns
5. Time zone handling and conversions
6. Scheduler persistence after restart (initialize_persisted_schedules)
7. Duplicate execution prevention
8. Campaign schedule pause, resume, and cancellation
9. Automation rule creation, listing, updating, and deletion
10. Reminder dispatch after 24 hours without open event (controlled test clock)
11. Automation loop and duplicate reminder prevention
12. Provider delivery callback processing (POST /webhooks/delivery)
13. Delivery status transitions (Queued -> Sent -> Delivered, Failed)
14. Duplicate callback handling (idempotency via WebhookEvent)
15. Automatic retry after failure (process_automatic_retries)
16. Maximum three attempts ceiling enforcement
17. Retry interval gap enforcement (HTTP 429 when retry interval in effect)
18. Manual retry endpoint (POST /messages/{id}/retry)
19. Retry all failed messages endpoint (POST /campaigns/{id}/retry-failed and POST /messages/retry-failed)
20. Successful message retry prevention (cannot retry Delivered messages)
21. Recipient consent enforcement during retries
22. Campaign lifecycle status transitions (Approved -> Scheduled -> Running -> Completed)
23. Delivery summary API (GET /campaigns/{id}/delivery)
24. Task 13 and Task 14 regression compatibility (fallback attempts, tracking IDs, channels)
"""

import unittest
from unittest.mock import patch, AsyncMock
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
import json
import asyncio

from sqlalchemy import create_engine, select
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
from app.models.segment import Segment
from app.models.content_asset import ContentAsset
from app.models.content_variant import ContentVariant
from app.models.communication import Message, DeliveryLog, Feedback
from app.models.channel_config import ChannelConfiguration
from app.models.campaign_schedule import CampaignSchedule
from app.models.automation_rule import AutomationRule, AutomationExecutionLog
from app.models.webhook_event import WebhookEvent
from app.services import (
    scheduler_service,
    automation_service,
    delivery_tracking_service,
    retry_service,
)
from app.schemas.scheduling import (
    CampaignScheduleCreateRequest,
    AutomationRuleCreateRequest,
    DeliveryCallbackPayload,
)


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


class TestSchedulingAndDeliveryTask15(unittest.TestCase):
    """Full unit and integration test suite for Task 15."""

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

        def override_get_db():
            db = self.SessionLocal()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)

        # Patch scheduler_service.SessionLocal and retry_service.SessionLocal to use our in-memory engine
        self.patcher_sched_session = patch("app.services.scheduler_service.SessionLocal", self.SessionLocal)
        self.patcher_retry_session = patch("app.services.retry_service.SessionLocal", self.SessionLocal)
        self.patcher_auto_session = patch("app.services.automation_service.SessionLocal", self.SessionLocal)
        self.patcher_sched_session.start()
        self.patcher_retry_session.start()
        self.patcher_auto_session.start()

        # Seed data
        with self.SessionLocal() as db:
            seed_roles(db)

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
            db.add(self.admin_user)
            db.add(self.manager_user)

            # Target Audience Members
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
                preferred_channel="SMS",
                consent_status=False,  # Unconsented
            )
            db.add(self.citizen_consented)
            db.add(self.citizen_unconsented)

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
            db.add(self.campaign)

            # Content Assets (Approved)
            self.sms_asset = ContentAsset(
                id=401,
                campaign_id=self.campaign.id,
                title="Polio Pulse Announcement",
                body="National Polio Day is Sunday. Bring children under 5 to nearest booth.",
                category="Awareness",
                channel="SMS",
                source_language="en",
                review_status="Approved",
                created_by=self.manager_user.id,
            )
            self.email_asset = ContentAsset(
                id=402,
                campaign_id=self.campaign.id,
                title="Polio Pulse Email",
                body="Dear citizen, National Polio Day is Sunday.",
                category="Awareness",
                channel="Email",
                source_language="en",
                review_status="Approved",
                created_by=self.manager_user.id,
            )
            db.add(self.sms_asset)
            db.add(self.email_asset)

            self.variant_en = ContentVariant(
                id=501,
                source_content_id=self.sms_asset.id,
                campaign_id=self.campaign.id,
                channel="SMS",
                language="en",
                variant_title="Polio Sunday Alert",
                variant_body="National Polio Day is Sunday. Bring children under 5 to nearest booth.",
                review_status="Approved",
                created_by=self.manager_user.id,
            )
            self.variant_hi = ContentVariant(
                id=502,
                source_content_id=self.sms_asset.id,
                campaign_id=self.campaign.id,
                channel="SMS",
                language="hi",
                variant_title="पोलियो अलर्ट",
                variant_body="राष्ट्रीय पोलियो दिवस रविवार को है। 5 वर्ष से कम उम्र के बच्चों को टीका लगवाएं।",
                review_status="Approved",
                created_by=self.manager_user.id,
            )
            db.add(self.variant_en)
            db.add(self.variant_hi)

            # Default Channel Configurations (mock mode)
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
            ch_wa = ChannelConfiguration(
                channel="WhatsApp",
                is_enabled=True,
                provider_type="mock",
                sender_address="+1555010099",
                sender_name="MassComm WhatsApp",
                credentials={"phone_number_id": "1000000001"},
            )
            db.add(ch_sms)
            db.add(ch_email)
            db.add(ch_wa)

            db.commit()

        # Auth headers
        admin_token = create_access_token(self.admin_user.id)
        self.admin_headers = {"Authorization": f"Bearer {admin_token}"}
        manager_token = create_access_token(self.manager_user.id)
        self.manager_headers = {"Authorization": f"Bearer {manager_token}"}

    def tearDown(self):
        self.patcher_sched_session.stop()
        self.patcher_retry_session.stop()
        self.patcher_auto_session.stop()
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=self.engine)

    # -------------------------------------------------------------------------
    # 1. Immediate Campaign Execution
    # -------------------------------------------------------------------------
    def test_01_immediate_campaign_execution(self):
        """schedule_type='now' immediately executes campaign distribution and marks Completed."""
        payload = {
            "schedule_type": "now",
            "timezone": "Asia/Kolkata",
            "channels": ["SMS"],
            "enable_fallback": False,
        }
        resp = self.client.post(
            f"/campaigns/{self.campaign.id}/schedule",
            json=payload,
            headers=self.manager_headers,
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["schedule_type"], "once")
        self.assertEqual(data["status"], "completed")
        self.assertEqual(data["execution_count"], 1)

        with self.SessionLocal() as db:
            camp = db.get(Campaign, self.campaign.id)
            self.assertEqual(camp.status, "Completed")
            msgs = db.execute(select(Message).where(Message.campaign_id == self.campaign.id)).scalars().all()
            self.assertGreaterEqual(len(msgs), 1)

    # -------------------------------------------------------------------------
    # 2. Future Campaign Scheduling
    # -------------------------------------------------------------------------
    def test_02_future_campaign_scheduling(self):
        """schedule_type='once' with future scheduled_at transitions campaign to Scheduled."""
        future_dt = datetime.now(timezone.utc) + timedelta(days=2)
        payload = {
            "schedule_type": "once",
            "scheduled_at": future_dt.isoformat(),
            "timezone": "UTC",
            "channels": ["SMS", "Email"],
            "enable_fallback": True,
        }
        resp = self.client.post(
            f"/campaigns/{self.campaign.id}/schedule",
            json=payload,
            headers=self.manager_headers,
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["schedule_type"], "once")
        self.assertEqual(data["status"], "active")
        self.assertIsNotNone(data["next_run_at"])

        with self.SessionLocal() as db:
            camp = db.get(Campaign, self.campaign.id)
            self.assertEqual(camp.status, "Scheduled")
            sc = db.execute(select(CampaignSchedule).where(CampaignSchedule.campaign_id == self.campaign.id)).scalar_one_or_none()
            self.assertIsNotNone(sc)
            self.assertEqual(sc.status, "active")

    # -------------------------------------------------------------------------
    # 3. Daily Recurring Campaigns
    # -------------------------------------------------------------------------
    def test_03_daily_recurring_campaign(self):
        """schedule_type='daily' with recurrence_time registers recurring schedule."""
        payload = {
            "schedule_type": "daily",
            "recurrence_time": "14:30",
            "timezone": "Asia/Kolkata",
            "channels": ["SMS"],
        }
        resp = self.client.post(
            f"/campaigns/{self.campaign.id}/schedule",
            json=payload,
            headers=self.manager_headers,
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["schedule_type"], "daily")
        self.assertEqual(data["recurrence_time"], "14:30")
        self.assertEqual(data["timezone"], "Asia/Kolkata")
        self.assertIsNotNone(data["next_run_at"])

    # -------------------------------------------------------------------------
    # 4. Weekly Recurring Campaigns
    # -------------------------------------------------------------------------
    def test_04_weekly_recurring_campaign(self):
        """schedule_type='weekly' with recurrence_days and recurrence_time."""
        payload = {
            "schedule_type": "weekly",
            "recurrence_days": ["mon", "wed", "fri"],
            "recurrence_time": "09:00",
            "timezone": "America/New_York",
            "channels": ["Email"],
        }
        resp = self.client.post(
            f"/campaigns/{self.campaign.id}/schedule",
            json=payload,
            headers=self.manager_headers,
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["schedule_type"], "weekly")
        self.assertEqual(data["recurrence_days"], ["mon", "wed", "fri"])
        self.assertIsNotNone(data["next_run_at"])

    # -------------------------------------------------------------------------
    # 5. Time Zone Handling
    # -------------------------------------------------------------------------
    def test_05_timezone_handling(self):
        """Tests timezone parsing and graceful fallback to UTC for unrecognized names."""
        tz_kolkata = scheduler_service.get_timezone_obj("Asia/Kolkata")
        self.assertEqual(tz_kolkata.key, "Asia/Kolkata")

        tz_invalid = scheduler_service.get_timezone_obj("Invalid/Timezone_Name")
        self.assertEqual(tz_invalid.key, "UTC")

    # -------------------------------------------------------------------------
    # 6. Scheduler Persistence After Restart
    # -------------------------------------------------------------------------
    def test_06_scheduler_persistence_after_restart(self):
        """Verifies active schedules in DB are reloaded into APScheduler upon restart."""
        with self.SessionLocal() as db:
            future_dt = datetime.now(timezone.utc) + timedelta(hours=5)
            sc = CampaignSchedule(
                campaign_id=self.campaign.id,
                schedule_type="once",
                scheduled_at=future_dt,
                status="active",
                timezone="UTC",
            )
            db.add(sc)
            db.commit()

        # Simulate restart
        with patch.object(scheduler_service.scheduler, "add_job") as mock_add_job:
            scheduler_service.initialize_persisted_schedules()
            self.assertTrue(mock_add_job.called)

    # -------------------------------------------------------------------------
    # 7. Duplicate Execution Prevention
    # -------------------------------------------------------------------------
    def test_07_duplicate_execution_prevention(self):
        """If a campaign is already Running, background execution skips to avoid double-sends."""
        with self.SessionLocal() as db:
            camp = db.get(Campaign, self.campaign.id)
            camp.status = "Running"  # Already running
            sc = CampaignSchedule(
                campaign_id=self.campaign.id,
                schedule_type="once",
                status="active",
                timezone="UTC",
            )
            db.add(sc)
            db.commit()

        # Run job
        asyncio.run(scheduler_service.execute_scheduled_campaign_job(self.campaign.id))

        with self.SessionLocal() as db:
            sc = db.execute(select(CampaignSchedule).where(CampaignSchedule.campaign_id == self.campaign.id)).scalar_one()
            self.assertEqual(sc.execution_count, 0)  # Skipped!

    # -------------------------------------------------------------------------
    # 8. Campaign Pause and Cancellation
    # -------------------------------------------------------------------------
    def test_08_campaign_pause_and_cancellation(self):
        """Tests pause, resume, and cancel schedule lifecycle."""
        with self.SessionLocal() as db:
            sc = CampaignSchedule(
                campaign_id=self.campaign.id,
                schedule_type="daily",
                recurrence_time="11:00",
                status="active",
                timezone="UTC",
            )
            db.add(sc)
            db.commit()

        # 1. Pause
        resp_pause = self.client.post(f"/campaigns/{self.campaign.id}/schedule/pause", headers=self.manager_headers)
        self.assertEqual(resp_pause.status_code, 200)
        self.assertEqual(resp_pause.json()["status"], "paused")

        # 2. Resume
        resp_resume = self.client.post(f"/campaigns/{self.campaign.id}/schedule/resume", headers=self.manager_headers)
        self.assertEqual(resp_resume.status_code, 200)
        self.assertEqual(resp_resume.json()["status"], "active")

        # 3. Cancel
        resp_cancel = self.client.delete(f"/campaigns/{self.campaign.id}/schedule", headers=self.manager_headers)
        self.assertEqual(resp_cancel.status_code, 200)

        with self.SessionLocal() as db:
            sc = db.execute(select(CampaignSchedule).where(CampaignSchedule.campaign_id == self.campaign.id)).scalar_one()
            self.assertEqual(sc.status, "cancelled")

    # -------------------------------------------------------------------------
    # 9. Automation Rule Creation, Listing, Updating, Deleting
    # -------------------------------------------------------------------------
    def test_09_automation_rule_crud(self):
        """Tests CRUD endpoints for campaign automation rules."""
        # Create
        payload = {
            "name": "24h Unread Follow-up",
            "trigger_condition": "message_not_opened",
            "wait_hours": 24,
            "action_type": "send_reminder",
            "action_channel": "SMS",
            "custom_message": "Don't forget to visit your local polio booth on Sunday!",
        }
        res_create = self.client.post(
            f"/campaigns/{self.campaign.id}/automation-rules",
            json=payload,
            headers=self.manager_headers,
        )
        self.assertEqual(res_create.status_code, 201)
        rule_id = res_create.json()["id"]

        # List
        res_list = self.client.get(f"/campaigns/{self.campaign.id}/automation-rules", headers=self.manager_headers)
        self.assertEqual(res_list.status_code, 200)
        self.assertEqual(len(res_list.json()), 1)

        # Update
        res_update = self.client.put(
            f"/campaigns/{self.campaign.id}/automation-rules/{rule_id}",
            json={"wait_hours": 48},
            headers=self.manager_headers,
        )
        self.assertEqual(res_update.status_code, 200)
        self.assertEqual(res_update.json()["wait_hours"], 48)

        # Delete
        res_del = self.client.delete(
            f"/campaigns/{self.campaign.id}/automation-rules/{rule_id}",
            headers=self.manager_headers,
        )
        self.assertEqual(res_del.status_code, 200)

    # -------------------------------------------------------------------------
    # 10. Reminder Dispatch After 24h Without Open (Controlled Test Clock)
    # -------------------------------------------------------------------------
    def test_10_reminder_after_24h_without_open_event(self):
        """Simulates 24h elapsed since delivery with opened_at=None, verifying automated reminder dispatch."""
        with self.SessionLocal() as db:
            rule = AutomationRule(
                campaign_id=self.campaign.id,
                name="24h Unread SMS Reminder",
                trigger_condition="message_not_opened",
                wait_hours=24,
                action_type="send_reminder",
                action_channel="SMS",
                is_enabled=True,
            )
            db.add(rule)

            # Create message delivered 25 hours ago with opened_at=None
            now = datetime.now(timezone.utc)
            msg = Message(
                campaign_id=self.campaign.id,
                audience_member_id=self.citizen_consented.id,
                channel="Email",
                language="en",
                rendered_content="Initial email content",
                status="Delivered",
                delivered_at=now - timedelta(hours=25),
                opened_at=None,  # Not opened!
            )
            db.add(msg)
            db.commit()

        # Evaluate rules using current time
        executed = asyncio.run(
            automation_service.evaluate_campaign_automation_rules(
                db=self.SessionLocal(),
                campaign_id=self.campaign.id,
            )
        )
        self.assertEqual(executed, 1)

        with self.SessionLocal() as db:
            # Check execution log
            log = db.execute(select(AutomationExecutionLog)).scalar_one_or_none()
            self.assertIsNotNone(log)
            self.assertEqual(log.status, "success")
            self.assertEqual(log.target_channel, "SMS")

            # Check new reminder message was created
            msgs = db.execute(select(Message).where(Message.channel == "SMS")).scalars().all()
            self.assertGreaterEqual(len(msgs), 1)

    # -------------------------------------------------------------------------
    # 11. Automation Loop and Duplicate Reminder Prevention
    # -------------------------------------------------------------------------
    def test_11_automation_loop_prevention(self):
        """Verifies that running rule evaluator repeatedly does not resend duplicate reminders."""
        with self.SessionLocal() as db:
            rule = AutomationRule(
                campaign_id=self.campaign.id,
                name="24h Unread Reminder",
                trigger_condition="message_not_opened",
                wait_hours=24,
                action_type="send_reminder",
                action_channel="SMS",
                is_enabled=True,
            )
            db.add(rule)

            now = datetime.now(timezone.utc)
            msg = Message(
                campaign_id=self.campaign.id,
                audience_member_id=self.citizen_consented.id,
                channel="Email",
                language="en",
                rendered_content="Initial email content",
                status="Delivered",
                delivered_at=now - timedelta(hours=30),
                opened_at=None,
            )
            db.add(msg)
            db.commit()

        # First evaluation: fires 1 action
        count1 = asyncio.run(automation_service.evaluate_campaign_automation_rules(self.SessionLocal(), self.campaign.id))
        self.assertEqual(count1, 1)

        # Second evaluation: deduplication prevents second run (loop prevention)
        count2 = asyncio.run(automation_service.evaluate_campaign_automation_rules(self.SessionLocal(), self.campaign.id))
        self.assertEqual(count2, 0)

    # -------------------------------------------------------------------------
    # 12. Provider Delivery Callback Processing
    # -------------------------------------------------------------------------
    def test_12_provider_delivery_callback_processing(self):
        """POST /webhooks/delivery updates message status to Delivered and sets delivered_at."""
        with self.SessionLocal() as db:
            msg = Message(
                tracking_id="trk_task15_test_cb_1",
                campaign_id=self.campaign.id,
                audience_member_id=self.citizen_consented.id,
                channel="SMS",
                language="en",
                rendered_content="Testing delivery callback",
                status="Sent",
                provider_message_id="SM_prov_12345",
            )
            db.add(msg)
            db.commit()

        payload = {
            "provider": "twilio",
            "provider_message_id": "SM_prov_12345",
            "status": "delivered",
        }
        resp = self.client.post("/webhooks/delivery", json=payload)
        self.assertEqual(resp.status_code, 200)

        with self.SessionLocal() as db:
            m = db.execute(select(Message).where(Message.tracking_id == "trk_task15_test_cb_1")).scalar_one()
            self.assertEqual(m.status, "Delivered")
            self.assertIsNotNone(m.delivered_at)

    # -------------------------------------------------------------------------
    # 13. Delivery Status Transitions
    # -------------------------------------------------------------------------
    def test_13_delivery_status_transitions(self):
        """Verifies Queued -> Sent -> Delivered, and that sent does NOT mark Delivered."""
        with self.SessionLocal() as db:
            msg = Message(
                tracking_id="trk_task15_test_trans_1",
                campaign_id=self.campaign.id,
                audience_member_id=self.citizen_consented.id,
                channel="Email",
                language="en",
                rendered_content="Status transition test",
                status="Queued",
                provider_message_id="EM_prov_777",
            )
            db.add(msg)
            db.commit()

        # Step 1: Provider accepts -> status is Sent (NOT Delivered)
        self.client.post(
            "/webhooks/delivery",
            json={"provider": "sendgrid", "provider_message_id": "EM_prov_777", "status": "sent"},
        )
        with self.SessionLocal() as db:
            m = db.execute(select(Message).where(Message.tracking_id == "trk_task15_test_trans_1")).scalar_one()
            self.assertEqual(m.status, "Sent")
            self.assertIsNone(m.delivered_at)

        # Step 2: Provider confirms receipt -> status is Delivered
        self.client.post(
            "/webhooks/delivery",
            json={"provider": "sendgrid", "provider_message_id": "EM_prov_777", "status": "delivered"},
        )
        with self.SessionLocal() as db:
            m = db.execute(select(Message).where(Message.tracking_id == "trk_task15_test_trans_1")).scalar_one()
            self.assertEqual(m.status, "Delivered")
            self.assertIsNotNone(m.delivered_at)

    # -------------------------------------------------------------------------
    # 14. Duplicate Callback Handling (Idempotency)
    # -------------------------------------------------------------------------
    def test_14_duplicate_callback_handling(self):
        """Duplicate callbacks are acknowledged idempotently without duplicate audit logs."""
        with self.SessionLocal() as db:
            msg = Message(
                tracking_id="trk_task15_test_idem_1",
                campaign_id=self.campaign.id,
                audience_member_id=self.citizen_consented.id,
                channel="SMS",
                language="en",
                rendered_content="Idempotency test",
                status="Sent",
                provider_message_id="SM_prov_dup_1",
            )
            db.add(msg)
            db.commit()

        cb_payload = {
            "provider": "fast2sms",
            "provider_message_id": "SM_prov_dup_1",
            "status": "delivered",
        }
        res1 = self.client.post("/webhooks/delivery", json=cb_payload)
        self.assertEqual(res1.status_code, 200)

        res2 = self.client.post("/webhooks/delivery", json=cb_payload)
        self.assertEqual(res2.status_code, 200)
        self.assertIn("Duplicate", res2.json()["message"])

        with self.SessionLocal() as db:
            logs = db.execute(select(DeliveryLog).where(DeliveryLog.message_id == msg.id)).scalars().all()
            self.assertEqual(len(logs), 1)  # Only 1 log entry created!

    # -------------------------------------------------------------------------
    # 15. Automatic Retry After Failure
    # -------------------------------------------------------------------------
    def test_15_automatic_retry_after_failure(self):
        """Failed message ready for retry (next_retry_at <= now) is retried by background worker."""
        now = datetime.now(timezone.utc)
        with self.SessionLocal() as db:
            msg = Message(
                campaign_id=self.campaign.id,
                audience_member_id=self.citizen_consented.id,
                channel="SMS",
                language="en",
                rendered_content="Automatic retry test",
                status="Failed",
                failure_reason="Carrier temporary timeout",
                retry_count=0,
                max_retries=3,
                next_retry_at=now - timedelta(minutes=1),  # Eligible for retry!
            )
            db.add(msg)
            db.commit()
            msg_id = msg.id

        asyncio.run(retry_service.process_automatic_retries())

        with self.SessionLocal() as db:
            m = db.get(Message, msg_id)
            self.assertEqual(m.retry_count, 1)
            self.assertIn(m.status, ("Sent", "Delivered"))

    # -------------------------------------------------------------------------
    # 16. Maximum Three Attempts Enforcement
    # -------------------------------------------------------------------------
    def test_16_maximum_three_attempts_enforcement(self):
        """Retrying a message with retry_count >= 3 is rejected with HTTP 400."""
        with self.SessionLocal() as db:
            msg = Message(
                campaign_id=self.campaign.id,
                audience_member_id=self.citizen_consented.id,
                channel="SMS",
                language="en",
                rendered_content="Three attempts limit test",
                status="Failed",
                retry_count=3,
                max_retries=3,
            )
            db.add(msg)
            db.commit()
            msg_id = msg.id

        resp = self.client.post(f"/messages/{msg_id}/retry", headers=self.manager_headers)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("maximum allowed retry attempts", resp.json()["detail"].lower())

    # -------------------------------------------------------------------------
    # 17. Retry Interval Enforcement
    # -------------------------------------------------------------------------
    def test_17_retry_interval_enforcement(self):
        """When next_retry_at is in the future, non-forced retry raises HTTP 429."""
        future_retry = datetime.now(timezone.utc) + timedelta(minutes=4)
        with self.SessionLocal() as db:
            msg = Message(
                campaign_id=self.campaign.id,
                audience_member_id=self.citizen_consented.id,
                channel="SMS",
                language="en",
                rendered_content="Interval gap test",
                status="Failed",
                retry_count=1,
                max_retries=3,
                next_retry_at=future_retry,
            )
            db.add(msg)
            db.commit()
            msg_id = msg.id

        resp = self.client.post(f"/messages/{msg_id}/retry?force=false", headers=self.manager_headers)
        self.assertEqual(resp.status_code, 429)
        self.assertIn("retry interval in effect", resp.json()["detail"].lower())

    # -------------------------------------------------------------------------
    # 18. Manual Retry API
    # -------------------------------------------------------------------------
    def test_18_manual_retry_api(self):
        """POST /messages/{id}/retry manually triggers message dispatch and increments retry count."""
        with self.SessionLocal() as db:
            msg = Message(
                campaign_id=self.campaign.id,
                audience_member_id=self.citizen_consented.id,
                channel="SMS",
                language="en",
                rendered_content="Manual retry API test",
                status="Failed",
                retry_count=0,
                max_retries=3,
            )
            db.add(msg)
            db.commit()
            msg_id = msg.id

        resp = self.client.post(f"/messages/{msg_id}/retry?force=true", headers=self.manager_headers)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["retry_count"], 1)
        self.assertTrue(data["success"])

        with self.SessionLocal() as db:
            m = db.get(Message, msg_id)
            self.assertEqual(m.retry_count, 1)
            self.assertIn(m.status, ("Sent", "Delivered"))

    # -------------------------------------------------------------------------
    # 19. Retry All Failed API
    # -------------------------------------------------------------------------
    def test_19_retry_all_failed_api(self):
        """POST /campaigns/{id}/retry-failed retries all eligible failed messages."""
        with self.SessionLocal() as db:
            msg1 = Message(
                campaign_id=self.campaign.id,
                audience_member_id=self.citizen_consented.id,
                channel="SMS",
                language="en",
                rendered_content="Batch retry 1",
                status="Failed",
                retry_count=0,
                max_retries=3,
            )
            msg2 = Message(
                campaign_id=self.campaign.id,
                audience_member_id=self.citizen_consented.id,
                channel="SMS",
                language="en",
                rendered_content="Batch retry 2",
                status="Failed",
                retry_count=1,
                max_retries=3,
            )
            db.add(msg1)
            db.add(msg2)
            db.commit()

        resp = self.client.post(f"/campaigns/{self.campaign.id}/retry-failed", headers=self.manager_headers)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["retried_count"], 2)
        self.assertEqual(data["succeeded_count"], 2)

    # -------------------------------------------------------------------------
    # 20. Successful Message Retry Prevention
    # -------------------------------------------------------------------------
    def test_20_successful_message_retry_prevention(self):
        """Attempting to retry a Delivered message raises HTTP 400."""
        with self.SessionLocal() as db:
            msg = Message(
                campaign_id=self.campaign.id,
                audience_member_id=self.citizen_consented.id,
                channel="SMS",
                language="en",
                rendered_content="Delivered message",
                status="Delivered",
            )
            db.add(msg)
            db.commit()
            msg_id = msg.id

        resp = self.client.post(f"/messages/{msg_id}/retry", headers=self.manager_headers)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("already delivered", resp.json()["detail"].lower())

    # -------------------------------------------------------------------------
    # 21. Consent Enforcement During Retries
    # -------------------------------------------------------------------------
    def test_21_consent_enforcement_during_retries(self):
        """Retrying a message for a citizen without affirmative consent is strictly blocked."""
        with self.SessionLocal() as db:
            msg = Message(
                campaign_id=self.campaign.id,
                audience_member_id=self.citizen_unconsented.id,  # consent_status=False
                channel="SMS",
                language="en",
                rendered_content="Unconsented retry test",
                status="Failed",
                retry_count=0,
                max_retries=3,
            )
            db.add(msg)
            db.commit()
            msg_id = msg.id

        resp = self.client.post(f"/messages/{msg_id}/retry", headers=self.manager_headers)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("consent", resp.json()["detail"].lower())

    # -------------------------------------------------------------------------
    # 22. Campaign Status Transitions
    # -------------------------------------------------------------------------
    def test_22_campaign_status_transitions(self):
        """Verifies campaign lifecycle states transition: Approved -> Scheduled -> Running -> Completed."""
        with self.SessionLocal() as db:
            camp = db.get(Campaign, self.campaign.id)
            self.assertEqual(camp.status, "Approved")

        # Schedule
        future_dt = datetime.now(timezone.utc) + timedelta(days=1)
        self.client.post(
            f"/campaigns/{self.campaign.id}/schedule",
            json={"schedule_type": "once", "scheduled_at": future_dt.isoformat()},
            headers=self.manager_headers,
        )
        with self.SessionLocal() as db:
            camp = db.get(Campaign, self.campaign.id)
            self.assertEqual(camp.status, "Scheduled")

        # Execute scheduled job
        asyncio.run(scheduler_service.execute_scheduled_campaign_job(self.campaign.id))
        with self.SessionLocal() as db:
            camp = db.get(Campaign, self.campaign.id)
            self.assertEqual(camp.status, "Completed")

    # -------------------------------------------------------------------------
    # 23. Delivery Summary API
    # -------------------------------------------------------------------------
    def test_23_delivery_summary_api(self):
        """GET /campaigns/{id}/delivery returns comprehensive tracking metrics."""
        with self.SessionLocal() as db:
            now = datetime.now(timezone.utc)
            m1 = Message(
                campaign_id=self.campaign.id,
                audience_member_id=self.citizen_consented.id,
                channel="SMS",
                language="en",
                rendered_content="Msg 1",
                status="Delivered",
                delivered_at=now,
                opened_at=now,
            )
            m2 = Message(
                campaign_id=self.campaign.id,
                audience_member_id=self.citizen_consented.id,
                channel="Email",
                language="en",
                rendered_content="Msg 2",
                status="Failed",
                failure_reason="Mailbox full",
                retry_count=1,
            )
            db.add(m1)
            db.add(m2)
            db.commit()

        resp = self.client.get(f"/campaigns/{self.campaign.id}/delivery", headers=self.manager_headers)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["total_messages"], 2)
        self.assertEqual(data["delivered_count"], 1)
        self.assertEqual(data["failed_count"], 1)
        self.assertEqual(data["opened_count"], 1)
        self.assertEqual(data["retried_count"], 1)
        self.assertIn("SMS", data["channel_breakdown"])
        self.assertIn("Email", data["channel_breakdown"])

    # -------------------------------------------------------------------------
    # 24. Task 13 & 14 Regression Compatibility
    # -------------------------------------------------------------------------
    def test_24_task13_and_task14_regression_compatibility(self):
        """Verifies multi-channel fallback attempt history and tracking IDs remain intact."""
        with self.SessionLocal() as db:
            msg = Message(
                tracking_id="trk_task14_compat_1",
                campaign_id=self.campaign.id,
                audience_member_id=self.citizen_consented.id,
                channel="SMS",
                language="en",
                rendered_content="Compatibility test",
                status="Delivered",
                fallback_attempts=[
                    {"channel": "WhatsApp", "status": "Failed", "failure_reason": "Not on WhatsApp"},
                    {"channel": "SMS", "status": "Delivered"},
                ],
            )
            db.add(msg)
            db.commit()

        # Check failed messages API returns fallback attempts
        resp = self.client.get("/messages/failed", headers=self.manager_headers)
        self.assertEqual(resp.status_code, 200)

        # Check open tracking pixel endpoint works
        resp_pixel = self.client.get("/webhooks/open/trk_task14_compat_1")
        self.assertEqual(resp_pixel.status_code, 200)
        self.assertEqual(resp_pixel.headers["content-type"], "image/gif")

        with self.SessionLocal() as db:
            m = db.execute(select(Message).where(Message.tracking_id == "trk_task14_compat_1")).scalar_one()
            self.assertIsNotNone(m.opened_at)
            self.assertEqual(len(m.fallback_attempts), 2)


if __name__ == "__main__":
    unittest.main()
