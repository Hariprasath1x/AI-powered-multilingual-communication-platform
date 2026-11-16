"""Automated Unit and Integration Tests for Milestone 3, Task 13: Channel Integration (Email & SMS).

Covers:
- Channel abstraction interface and registry extensibility
- EmailChannel and SMSChannel mock/demo mode and deterministic failures
- Campaign approval verification and rejection of unapproved campaigns
- Recipient preferred channel and language/variant selection
- Affirmative consent enforcement and opt-out exclusion
- Message tracking persistence (unique tracking ID, provider ID, status)
- Administrative channel configuration and connectivity test endpoints
- Campaign send and live summary APIs
"""

import unittest
from unittest.mock import patch, AsyncMock
from datetime import datetime, timezone
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
from app.models.segment import Segment
from app.models.content_asset import ContentAsset
from app.models.content_variant import ContentVariant
from app.models.communication import Message
from app.models.channel_config import ChannelConfiguration
from app.services.channels import (
    BaseChannel,
    ChannelSendResult,
    EmailChannel,
    SMSChannel,
    register_channel,
    get_channel,
    get_configured_channel,
)
from app.schemas.channel_config import mask_secret


def seed_default_roles(db):
    roles = [
        Role(id=1, name="Admin", description="System administrator"),
        Role(id=2, name="Campaign Manager", description="Campaign manager"),
        Role(id=3, name="Communication Team", description="Communication staff"),
    ]
    for r in roles:
        if not db.get(Role, r.id):
            db.add(r)
    db.commit()


class TestChannelIntegration(unittest.TestCase):
    """Test suite for Task 13: Channel Integration (Email & SMS)."""

    def setUp(self):
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=self.engine)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        self.db = self.SessionLocal()
        seed_default_roles(self.db)

        # Users
        self.admin_user = User(
            email="admin@channels.gov.in",
            hashed_password=get_password_hash("Secret123!"),
            full_name="Platform Admin",
            role_id=1,
            organization="Central Ministry",
            is_active=True,
        )
        self.manager_user = User(
            email="manager@channels.gov.in",
            hashed_password=get_password_hash("Secret123!"),
            full_name="Campaign Manager",
            role_id=2,
            organization="Central Ministry",
            is_active=True,
        )
        self.comm_user = User(
            email="comm@channels.gov.in",
            hashed_password=get_password_hash("Secret123!"),
            full_name="Communications Specialist",
            role_id=3,
            organization="Central Ministry",
            is_active=True,
        )
        self.db.add_all([self.admin_user, self.manager_user, self.comm_user])
        self.db.commit()

        # Seed default channel configurations
        self.email_config = ChannelConfiguration(
            channel="Email",
            is_enabled=True,
            provider_type="mock",
            sender_address="notifications@masscomm.gov.in",
            sender_name="MassCommAI Citizen Communications",
            credentials={"smtp_host": "smtp.masscomm.gov.in"},
        )
        self.sms_config = ChannelConfiguration(
            channel="SMS",
            is_enabled=True,
            provider_type="mock",
            sender_address="GOVMSG",
            sender_name="Govt Citizen Alert",
            credentials={"sender_id": "GOVMSG"},
        )
        self.db.add_all([self.email_config, self.sms_config])
        self.db.commit()

        # Campaign setup
        self.campaign = Campaign(
            name="Flood Relief Alert 2026",
            campaign_type="Emergency Alert",
            objective="Emergency safety alert for coastal citizens",
            priority="High",
            status="Approved",
            channels=["Email", "SMS"],
            created_by=self.manager_user.id,
        )
        self.db.add(self.campaign)
        self.db.commit()

        # Content Assets (Approved)
        self.root_email_asset = ContentAsset(
            title="Flood Safety Notice",
            body="Dear {name}, coastal storm surge warning in {city}. Helplines: 1077.",
            category="Emergency Alert",
            channel="Email",
            source_language="en",
            review_status="Approved",
            campaign_id=self.campaign.id,
            created_by=self.manager_user.id,
        )
        self.hindi_email_asset = ContentAsset(
            title="बाढ़ सुरक्षा चेतावनी",
            body="प्रिय {name}, {city} में बाढ़ की चेतावनी। हेल्पलाइन: 1077.",
            category="Emergency Alert",
            channel="Email",
            source_language="en",
            target_language="hi",
            review_status="Approved",
            campaign_id=self.campaign.id,
            created_by=self.manager_user.id,
        )
        self.root_sms_asset = ContentAsset(
            title="Emergency SMS",
            body="ALERT: Storm warning for {name} in {city}. Evacuate immediately. Helpline: 1077.",
            category="Emergency Alert",
            channel="SMS",
            source_language="en",
            review_status="Approved",
            campaign_id=self.campaign.id,
            created_by=self.manager_user.id,
        )
        self.hindi_sms_asset = ContentAsset(
            title="आपातकालीन एसएमएस",
            body="चेतावनी: {city} में {name} तुरंत सुरक्षित स्थान पर जाएं। हेल्पलाइन 1077.",
            category="Emergency Alert",
            channel="SMS",
            source_language="en",
            target_language="hi",
            review_status="Approved",
            campaign_id=self.campaign.id,
            created_by=self.manager_user.id,
        )
        self.db.add_all([
            self.root_email_asset,
            self.hindi_email_asset,
            self.root_sms_asset,
            self.hindi_sms_asset,
        ])
        self.db.commit()

        # Audience Members with varying consent and preferences
        # 1. Consented Email English
        self.member_email_en = AudienceMember(
            name="Aarav Sharma",
            email="aarav@example.gov.in",
            phone="+919876543210",
            city="Chennai",
            state="Tamil Nadu",
            preferred_language="en",
            preferred_channel="Email",
            consent_status=True,
        )
        # 2. Consented SMS Hindi
        self.member_sms_hi = AudienceMember(
            name="Priya Patel",
            email="priya@example.gov.in",
            phone="+919876543211",
            city="Mumbai",
            state="Maharashtra",
            preferred_language="hi",
            preferred_channel="SMS",
            consent_status=True,
        )
        # 3. Opted-out Member (consent_status=False)
        self.member_opted_out = AudienceMember(
            name="Rohan Verma",
            email="rohan@example.gov.in",
            phone="+919876543212",
            city="Delhi",
            preferred_language="en",
            preferred_channel="Email",
            consent_status=False,
        )
        # 4. Unconfirmed Member (consent_status=None)
        self.member_unconfirmed = AudienceMember(
            name="Ananya Roy",
            email="ananya@example.gov.in",
            phone="+919876543213",
            city="Kolkata",
            preferred_language="en",
            preferred_channel="Email",
            consent_status=None,
        )
        # 5. Deterministic Fail Recipient (Email fail_perm)
        self.member_fail_email = AudienceMember(
            name="Bounced User",
            email="bounced_fail_perm@example.gov.in",
            phone="+919876543214",
            city="Pune",
            preferred_language="en",
            preferred_channel="Email",
            consent_status=True,
        )
        self.db.add_all([
            self.member_email_en,
            self.member_sms_hi,
            self.member_opted_out,
            self.member_unconfirmed,
            self.member_fail_email,
        ])
        self.db.commit()

        # Test client with dependency override
        def override_get_db():
            db = self.SessionLocal()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)

        # Auth Tokens
        self.admin_token = create_access_token(self.admin_user.id)
        self.manager_token = create_access_token(self.manager_user.id)
        self.comm_token = create_access_token(self.comm_user.id)

    def tearDown(self):
        app.dependency_overrides.clear()
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)

    # -------------------------------------------------------------------------
    # 1. Channel Abstraction & Extensibility Tests
    # -------------------------------------------------------------------------

    def test_channel_abstraction_interface(self):
        """Verifies BaseChannel interface contracts and ChannelRegistry dynamic registration."""
        email_channel = get_channel("Email")
        self.assertIsInstance(email_channel, BaseChannel)
        self.assertEqual(email_channel.get_channel_name(), "Email")

        sms_channel = get_channel("SMS")
        self.assertIsInstance(sms_channel, BaseChannel)
        self.assertEqual(sms_channel.get_channel_name(), "SMS")

        # Custom Channel Registration
        class MockWhatsAppChannel(BaseChannel):
            def get_channel_name(self):
                return "WhatsApp"
            async def send(self, message, recipient):
                return ChannelSendResult(
                    success=True,
                    status="Delivered",
                    provider_name="mock_whatsapp",
                    provider_message_id="wa_123",
                )
            def validate_recipient(self, recipient):
                return True, None
            async def send_test(self, destination, body, subject=None, config_override=None):
                return ChannelSendResult(success=True, status="Delivered", provider_name="mock_whatsapp")

        register_channel("WhatsApp", MockWhatsAppChannel())
        wa = get_channel("WhatsApp")
        self.assertEqual(wa.get_channel_name(), "WhatsApp")

    # -------------------------------------------------------------------------
    # 2. Email Provider Integration & Mock Mode Tests
    # -------------------------------------------------------------------------

    async def _run_async(self, coro):
        return await coro

    def test_email_channel_mock_successful_delivery(self):
        """EmailChannel in mock mode dispatches successfully with valid tracking ID and provider reference."""
        import asyncio
        channel = EmailChannel(provider_type="mock")

        class DummyRecipient:
            email = "citizen@example.gov.in"
            name = "Citizen"

        class DummyMessage:
            tracking_id = "trk_email_test_123"
            subject = "Safety Notice"
            rendered_content = "Please stay indoors."

        result = asyncio.run(channel.send(DummyMessage(), DummyRecipient()))
        self.assertTrue(result.success)
        self.assertEqual(result.status, "Delivered")
        self.assertEqual(result.provider_name, "mock_email")
        self.assertIn("mock-email-", result.provider_message_id)

    def test_email_channel_mock_deterministic_failures(self):
        """EmailChannel handles permanent bounce, temporary throttling, and invalid format."""
        import asyncio
        channel = EmailChannel(provider_type="mock")

        class PermRecipient:
            email = "user_fail_perm@example.gov.in"
            name = "Perm Fail"
        class TempRecipient:
            email = "user_fail_temp@example.gov.in"
            name = "Temp Fail"
        class InvalidRecipient:
            email = "not-an-email"
            name = "Invalid"

        class DummyMsg:
            tracking_id = "trk_err"
            rendered_content = "Test"

        # Perm bounce
        res_perm = asyncio.run(channel.send(DummyMsg(), PermRecipient()))
        self.assertFalse(res_perm.success)
        self.assertEqual(res_perm.error_code, "RECIPIENT_MAILBOX_NOT_FOUND")

        # Temp busy
        res_temp = asyncio.run(channel.send(DummyMsg(), TempRecipient()))
        self.assertFalse(res_temp.success)
        self.assertEqual(res_temp.error_code, "SMTP_421_SERVICE_BUSY")

        # Invalid format
        res_inv = asyncio.run(channel.send(DummyMsg(), InvalidRecipient()))
        self.assertFalse(res_inv.success)
        self.assertEqual(res_inv.error_code, "INVALID_EMAIL_FORMAT")

    # -------------------------------------------------------------------------
    # 3. SMS Provider Integration & Mock Mode Tests
    # -------------------------------------------------------------------------

    def test_sms_channel_mock_successful_delivery(self):
        """SMSChannel in mock mode dispatches with segment calculation and tracking."""
        import asyncio
        channel = SMSChannel(provider_type="mock")

        class DummyRecipient:
            phone = "+919876543210"
            name = "Citizen"

        class DummyMessage:
            tracking_id = "trk_sms_test_123"
            rendered_content = "Cyclone warning: Coastal shelters are open. Emergency: 1077."

        result = asyncio.run(channel.send(DummyMessage(), DummyRecipient()))
        self.assertTrue(result.success)
        self.assertEqual(result.status, "Delivered")
        self.assertEqual(result.provider_name, "mock_sms")
        self.assertIn("mock-sms-", result.provider_message_id)
        self.assertEqual(result.metadata.get("segment_count"), 1)

    def test_sms_channel_mock_deterministic_failures(self):
        """SMSChannel handles unreachable destination, operator rate limit, and bad phone numbers."""
        import asyncio
        channel = SMSChannel(provider_type="mock")

        class PermPhone:
            phone = "+919870fail_perm"
        class TempPhone:
            phone = "+919870fail_temp"
        class InvalidPhone:
            phone = "123"

        class DummyMsg:
            tracking_id = "trk_sms_err"
            rendered_content = "Alert"

        res_perm = asyncio.run(channel.send(DummyMsg(), PermPhone()))
        self.assertFalse(res_perm.success)
        self.assertEqual(res_perm.error_code, "CARRIER_UNREACHABLE_DESTINATION")

        res_temp = asyncio.run(channel.send(DummyMsg(), TempPhone()))
        self.assertFalse(res_temp.success)
        self.assertEqual(res_temp.error_code, "CARRIER_RATE_LIMIT_EXCEEDED")

        res_inv = asyncio.run(channel.send(DummyMsg(), InvalidPhone()))
        self.assertFalse(res_inv.success)
        self.assertEqual(res_inv.error_code, "INVALID_PHONE_NUMBER")

    # -------------------------------------------------------------------------
    # 4. Campaign Sending API & Approval Validation Tests
    # -------------------------------------------------------------------------

    def test_rejection_of_unapproved_campaign(self):
        """POST /campaigns/{id}/send strictly rejects campaigns that are not 'Approved'."""
        draft_campaign = Campaign(
            name="Unapproved Draft Campaign",
            campaign_type="Awareness",
            status="Draft",
            channels=["Email"],
            created_by=self.manager_user.id,
        )
        self.db.add(draft_campaign)
        self.db.commit()

        resp = self.client.post(
            f"/campaigns/{draft_campaign.id}/send",
            headers={"Authorization": f"Bearer {self.manager_token}"},
            json={"channels": ["Email"]},
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Only campaigns with review status 'Approved' are permitted", resp.json()["detail"])

    def test_send_nonexistent_campaign_returns_404(self):
        """POST /campaigns/99999/send returns HTTP 404."""
        resp = self.client.post(
            "/campaigns/99999/send",
            headers={"Authorization": f"Bearer {self.manager_token}"},
            json={},
        )
        self.assertEqual(resp.status_code, 404)

    def test_unauthorized_user_forbidden_to_send(self):
        """Unauthenticated returns 401; Communication Specialist (read-only) returns 403."""
        # Unauthenticated
        resp_unauth = self.client.post(f"/campaigns/{self.campaign.id}/send", json={})
        self.assertEqual(resp_unauth.status_code, 401)

        # Comm Team (lacks CAMPAIGN_WRITE_ROLES)
        resp_comm = self.client.post(
            f"/campaigns/{self.campaign.id}/send",
            headers={"Authorization": f"Bearer {self.comm_token}"},
            json={},
        )
        self.assertEqual(resp_comm.status_code, 403)

    # -------------------------------------------------------------------------
    # 5. End-to-End Campaign Distribution & Consent Enforcement
    # -------------------------------------------------------------------------

    def test_successful_approved_campaign_broadcast_with_consent_and_multilingual_selection(self):
        """
        Executes complete campaign distribution:
        - Consented Email recipient receives English Email
        - Consented SMS recipient receives Hindi SMS
        - Opted out and unconfirmed recipients are withheld
        - Bounced email recipient is recorded as Failed
        - Campaign transitions to 'Completed'
        """
        resp = self.client.post(
            f"/campaigns/{self.campaign.id}/send",
            headers={"Authorization": f"Bearer {self.manager_token}"},
            json={"channels": ["Email", "SMS"]},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        self.assertEqual(data["campaign_id"], self.campaign.id)
        self.assertEqual(data["campaign_status"], "Completed")
        self.assertEqual(data["total_intended_recipients"], 5)
        self.assertEqual(data["opted_out_recipients"], 2)  # Rohan (False) and Ananya (None)
        self.assertEqual(data["eligible_recipients"], 3)  # Aarav, Priya, Bounced

        # Verify Channel Summary Cards
        self.assertIn("Email", data["channel_summary"])
        self.assertIn("SMS", data["channel_summary"])

        # Email stats: 3 attempted (Aarav Delivered, Bounced Failed, Rohan Opted-out Failed)
        self.assertGreaterEqual(data["channel_summary"]["Email"]["total"], 2)

        # Message Records Verification
        messages = data["messages"]
        self.assertEqual(len(messages), 5)

        # 1. Aarav (Email, en, consented) -> Delivered
        aarav_msg = next(m for m in messages if m["recipient_name"] == "Aarav Sharma")
        self.assertEqual(aarav_msg["channel"], "Email")
        self.assertEqual(aarav_msg["language"], "en")
        self.assertEqual(aarav_msg["status"], "Delivered")
        self.assertTrue(aarav_msg["tracking_id"].startswith("trk_"))
        self.assertIn("mock-email-", aarav_msg["provider_message_id"])

        # 2. Priya (SMS, hi, consented) -> Delivered in Hindi
        priya_msg = next(m for m in messages if m["recipient_name"] == "Priya Patel")
        self.assertEqual(priya_msg["channel"], "SMS")
        self.assertEqual(priya_msg["language"], "hi")
        self.assertEqual(priya_msg["status"], "Delivered")
        self.assertIn("mock-sms-", priya_msg["provider_message_id"])

        # 3. Rohan (Opted out) -> Failed with consent reason
        rohan_msg = next(m for m in messages if m["recipient_name"] == "Rohan Verma")
        self.assertEqual(rohan_msg["status"], "Failed")
        self.assertIn("opted out", rohan_msg["failure_reason"].lower())

        # 4. Ananya (Unconfirmed) -> Failed with unconfirmed reason
        ananya_msg = next(m for m in messages if m["recipient_name"] == "Ananya Roy")
        self.assertEqual(ananya_msg["status"], "Failed")
        self.assertIn("consent", ananya_msg["failure_reason"].lower())

        # 5. Bounced User -> Failed with provider error
        bounced_msg = next(m for m in messages if m["recipient_name"] == "Bounced User")
        self.assertEqual(bounced_msg["status"], "Failed")
        self.assertIn("Mailbox does not exist", bounced_msg["failure_reason"])

    def test_message_persistence_and_unique_tracking_ids_in_database(self):
        """Verifies that individual message records in 'messages' table have unique tracking IDs."""
        self.client.post(
            f"/campaigns/{self.campaign.id}/send",
            headers={"Authorization": f"Bearer {self.manager_token}"},
            json={},
        )

        db_messages = self.db.query(Message).filter(Message.campaign_id == self.campaign.id).all()
        self.assertEqual(len(db_messages), 5)

        tracking_ids = [m.tracking_id for m in db_messages]
        # Guarantee all tracking IDs are strictly unique
        self.assertEqual(len(tracking_ids), len(set(tracking_ids)))

        for m in db_messages:
            self.assertTrue(m.tracking_id.startswith("trk_"))
            self.assertIsNotNone(m.created_at)
            self.assertIsNotNone(m.updated_at)

    def test_get_campaign_send_summary_endpoint(self):
        """GET /campaigns/{id}/send/summary returns live aggregate counts and message records."""
        # Execute send
        self.client.post(
            f"/campaigns/{self.campaign.id}/send",
            headers={"Authorization": f"Bearer {self.manager_token}"},
            json={},
        )

        # Query summary
        resp = self.client.get(
            f"/campaigns/{self.campaign.id}/send/summary",
            headers={"Authorization": f"Bearer {self.comm_token}"},
        )
        self.assertEqual(resp.status_code, 200)
        summary = resp.json()
        self.assertEqual(summary["campaign_id"], self.campaign.id)
        self.assertEqual(summary["campaign_status"], "Completed")
        self.assertGreaterEqual(summary["delivered_messages"], 2)
        self.assertEqual(summary["opted_out_recipients"], 2)

    # -------------------------------------------------------------------------
    # 6. Admin Channel Settings & Diagnostic APIs
    # -------------------------------------------------------------------------

    def test_admin_list_and_update_channel_configuration(self):
        """Admin can list and update channel configurations with masked credentials."""
        # 1. List channels (Admin role)
        resp = self.client.get(
            "/admin/channels",
            headers={"Authorization": f"Bearer {self.admin_token}"},
        )
        self.assertEqual(resp.status_code, 200)
        channels = {c["channel"]: c for c in resp.json()}
        self.assertIn("Email", channels)
        self.assertIn("SMS", channels)
        self.assertTrue(channels["Email"]["is_enabled"])

        # Non-admins forbidden
        resp_forbidden = self.client.get(
            "/admin/channels",
            headers={"Authorization": f"Bearer {self.manager_token}"},
        )
        self.assertEqual(resp_forbidden.status_code, 403)

        # 2. Update Email channel configuration
        update_payload = {
            "is_enabled": True,
            "provider_type": "smtp",
            "sender_address": "alerts@disaster.gov.in",
            "sender_name": "Emergency Broadcast System",
            "credentials": {
                "smtp_host": "smtp.disaster.gov.in",
                "smtp_port": 587,
                "smtp_password": "SuperSecretPassword123",
            },
        }
        put_resp = self.client.put(
            "/admin/channels/Email",
            headers={"Authorization": f"Bearer {self.admin_token}"},
            json=update_payload,
        )
        self.assertEqual(put_resp.status_code, 200)
        updated = put_resp.json()
        self.assertEqual(updated["provider_type"], "smtp")
        self.assertEqual(updated["sender_address"], "alerts@disaster.gov.in")
        # Ensure password is masked
        self.assertTrue(updated["masked_credentials"]["smtp_password"].startswith("Sup****"))

    def test_admin_channel_connectivity_test_endpoint(self):
        """Admin can execute isolated connectivity test via POST /admin/channels/{channel}/test."""
        test_payload = {
            "destination": "qa_officer@gov.in",
            "message": "Probe verification",
            "subject": "Connectivity Test",
        }
        resp = self.client.post(
            "/admin/channels/Email/test",
            headers={"Authorization": f"Bearer {self.admin_token}"},
            json=test_payload,
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["status"], "Delivered")
        self.assertIn("mock-email-", data["provider_message_id"])

    def test_disabled_channel_withholds_dispatch(self):
        """Disabling a channel in channel_configurations causes messages on that channel to be blocked."""
        # Disable SMS channel
        sms_cfg = self.db.query(ChannelConfiguration).filter_by(channel="SMS").first()
        sms_cfg.is_enabled = False
        self.db.commit()

        resp = self.client.post(
            f"/campaigns/{self.campaign.id}/send",
            headers={"Authorization": f"Bearer {self.manager_token}"},
            json={"channels": ["SMS"]},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        # Priya prefers SMS, so she should be blocked with channel disabled reason
        priya_msg = next(m for m in data["messages"] if m["recipient_name"] == "Priya Patel")
        self.assertEqual(priya_msg["status"], "Failed")
        self.assertIn("disabled by administrator", priya_msg["failure_reason"])

    def test_credential_masking_utility(self):
        """mask_secret utility properly obscures tokens while preserving hints."""
        self.assertIsNone(mask_secret(None))
        self.assertEqual(mask_secret("123"), "****")
        self.assertEqual(mask_secret("12345678"), "12****")
        self.assertEqual(mask_secret("SG.abcdefghijklmnopqrstuvwxyz"), "SG.****xyz")


if __name__ == "__main__":
    unittest.main()
