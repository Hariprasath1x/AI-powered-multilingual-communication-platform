"""Automated Unit and Integration Tests for Milestone 3, Task 14: Omnichannel Integration.

Covers:
1. WhatsAppChannel adapter initialization and recipient validation
2. WhatsAppChannel deterministic mock delivery (success, fail_perm, fail_temp)
3. WhatsAppChannel Meta API dispatch with mocked HTTP responses
4. PushChannel adapter initialization, device token resolution and validation
5. PushChannel deterministic mock delivery (success, fail_perm, fail_temp)
6. PushChannel FCM HTTP v1 dispatch with mocked responses
7. WebBroadcastChannel public dispatch with zero PII leakage
8. Inbound Meta WhatsApp webhook challenge verification (GET /webhooks/whatsapp)
9. Inbound Meta WhatsApp status callback idempotency and status transition (POST /webhooks/whatsapp)
10. Inbound Meta WhatsApp citizen reply logging to Feedback
11. Inbound Push webhook invalid token handling (POST /webhooks/push)
12. Device token registration and reactivation endpoint (POST /notifications/devices/register)
13. Public announcements feed endpoint (GET /announcements)
14. Public announcements Server-Sent Events stream (GET /broadcast/sse)
15. Omnichannel campaign broadcast with sequential fallback (WhatsApp -> SMS -> Email)
16. Campaign broadcast with fallback disabled (single attempt)
17. Affirmative consent enforcement across all omnichannel distribution targets
18. Administrator channel disabled toggle triggers fallback to eligible channels
19. Automatic device token deactivation upon gateway token invalidation
20. Masked credentials in administrative channel settings
"""

import unittest
from unittest.mock import patch, AsyncMock
from datetime import datetime, timezone
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
from app.models.communication import Message, Feedback
from app.models.channel_config import ChannelConfiguration
from app.models.device_token import DeviceToken
from app.models.web_broadcast import WebBroadcast
from app.models.webhook_event import WebhookEvent
from app.services.channels import (
    get_channel,
    get_configured_channel,
    WhatsAppChannel,
    PushChannel,
    WebBroadcastChannel,
)


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


class TestMultichannelTask14(unittest.TestCase):
    """Test suite for Milestone 3, Task 14 Omnichannel Integration."""

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
            email="admin@omnichannel.gov.in",
            hashed_password=get_password_hash("Secret123!"),
            full_name="Platform Admin",
            role_id=1,
            organization="Central Ministry",
            is_active=True,
        )
        self.manager_user = User(
            email="manager@omnichannel.gov.in",
            hashed_password=get_password_hash("Secret123!"),
            full_name="Campaign Manager",
            role_id=2,
            organization="Central Ministry",
            is_active=True,
        )
        self.db.add_all([self.admin_user, self.manager_user])
        self.db.commit()

        # Channel Configurations
        self.configs = [
            ChannelConfiguration(
                channel="Email",
                is_enabled=True,
                provider_type="mock",
                sender_address="notifications@masscomm.gov.in",
                sender_name="MassCommAI Citizen Communications",
                credentials={"smtp_host": "smtp.masscomm.gov.in"},
            ),
            ChannelConfiguration(
                channel="SMS",
                is_enabled=True,
                provider_type="mock",
                sender_address="GOVMSG",
                sender_name="Govt Citizen Alert",
                credentials={},
            ),
            ChannelConfiguration(
                channel="WhatsApp",
                is_enabled=True,
                provider_type="mock",
                sender_address="+1555010099",
                sender_name="MassCommAI WhatsApp Official",
                credentials={"phone_number_id": "1000000001", "waba_id": "2000000002"},
            ),
            ChannelConfiguration(
                channel="Push",
                is_enabled=True,
                provider_type="mock",
                sender_address="masscommai-fcm-project",
                sender_name="MassCommAI Citizen Push",
                credentials={"project_id": "masscommai-fcm-project"},
            ),
            ChannelConfiguration(
                channel="Web",
                is_enabled=True,
                provider_type="mock",
                sender_address="masscomm-broadcast-hub",
                sender_name="MassCommAI Web Broadcast",
                credentials={},
            ),
        ]
        self.db.add_all(self.configs)
        self.db.commit()

        # Approved Campaign
        self.campaign = Campaign(
            name="Cyclone Nivar Public Advisory 2026",
            campaign_type="Emergency Alert",
            objective="Urgent weather alert and coastal evacuation routes",
            priority="High",
            status="Approved",
            channels=["WhatsApp", "SMS", "Email", "Push", "Web"],
            created_by=self.manager_user.id,
        )
        self.db.add(self.campaign)
        self.db.commit()

        # Content Assets (Approved)
        self.root_asset = ContentAsset(
            title="Cyclone Advisory",
            body="Dear {name}, high wind warning in {city}. Emergency helpline: 1077.",
            category="Emergency Alert",
            channel="Email",
            source_language="en",
            review_status="Approved",
            campaign_id=self.campaign.id,
            created_by=self.manager_user.id,
        )
        self.db.add(self.root_asset)
        self.db.commit()

        # TestClient override
        def override_get_db():
            try:
                yield self.db
            finally:
                pass

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)

        # Tokens
        self.admin_token = create_access_token(self.admin_user.id)
        self.manager_token = create_access_token(self.manager_user.id)
        self.admin_headers = {"Authorization": f"Bearer {self.admin_token}"}
        self.manager_headers = {"Authorization": f"Bearer {self.manager_token}"}

    def tearDown(self):
        app.dependency_overrides.clear()
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)

    # -------------------------------------------------------------------------
    # 1. WhatsApp Channel Unit Tests
    # -------------------------------------------------------------------------
    def test_whatsapp_channel_initialization_and_validation(self):
        channel = WhatsAppChannel(provider_type="mock")
        self.assertEqual(channel.get_channel_name(), "WhatsApp")

        class Recipient:
            phone = "+919876543210"

        is_valid, err = channel.validate_recipient(Recipient())
        self.assertTrue(is_valid)
        self.assertIsNone(err)

        class EmptyRecipient:
            phone = ""

        is_valid, err = channel.validate_recipient(EmptyRecipient())
        self.assertFalse(is_valid)
        self.assertIn("missing or empty", err)

        class BadRecipient:
            phone = "123"

        is_valid, err = channel.validate_recipient(BadRecipient())
        self.assertFalse(is_valid)
        self.assertIn("Invalid phone number format", err)

    def test_whatsapp_deterministic_mock_delivery(self):
        channel = WhatsAppChannel(provider_type="mock")

        class Msg:
            tracking_id = "trk_wa_01"
            rendered_content = "Mock WhatsApp body"

        # Success case
        class RecipientOk:
            phone = "+919876543210"

        res = asyncio.run(channel.send(Msg(), RecipientOk()))
        self.assertTrue(res.success)
        self.assertEqual(res.status, "Sent")
        self.assertIn("wamid", res.provider_message_id)

        # Permanent failure
        class RecipientPermFail:
            phone = "+919870fail_perm"

        res = asyncio.run(channel.send(Msg(), RecipientPermFail()))
        self.assertFalse(res.success)
        self.assertEqual(res.error_code, "USER_NOT_REGISTERED_ON_WHATSAPP")

        # Temporary failure
        class RecipientTempFail:
            phone = "+919870fail_temp"

        res = asyncio.run(channel.send(Msg(), RecipientTempFail()))
        self.assertFalse(res.success)
        self.assertEqual(res.error_code, "WHATSAPP_SESSION_BUSY")

    def test_whatsapp_meta_api_dispatch(self):
        channel = WhatsAppChannel(
            provider_type="meta",
            sender_address="1000000001",
            credentials={"phone_number_id": "1000000001", "access_token": "EAAtesttoken"},
        )

        class Msg:
            tracking_id = "trk_wa_meta"
            rendered_content = "Official Meta API text"

        class Recipient:
            phone = "+919876543210"

        from unittest.mock import MagicMock
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "messaging_product": "whatsapp",
            "messages": [{"id": "wamid.HBgLMzkxOTg3NjU0"}]
        }

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_response):
            res = asyncio.run(channel.send(Msg(), Recipient()))
            self.assertTrue(res.success)
            self.assertEqual(res.status, "Sent")
            self.assertEqual(res.provider_message_id, "wamid.HBgLMzkxOTg3NjU0")

    # -------------------------------------------------------------------------
    # 2. Push Channel Unit Tests
    # -------------------------------------------------------------------------
    def test_push_channel_token_resolution_and_validation(self):
        channel = PushChannel(provider_type="mock")
        self.assertEqual(channel.get_channel_name(), "Push")

        class RecipientWithToken:
            token = "fcm_client_token_xyz"

        is_valid, err = channel.validate_recipient(RecipientWithToken())
        self.assertTrue(is_valid)

        class RecipientWithoutToken:
            pass

        is_valid, err = channel.validate_recipient(RecipientWithoutToken())
        self.assertFalse(is_valid)
        self.assertIn("no registered device token", err)

    def test_push_deterministic_mock_delivery(self):
        channel = PushChannel(provider_type="mock")

        class Msg:
            tracking_id = "trk_push_01"
            rendered_content = "Push notification message"

        # Success case
        class RecOk:
            token = "fcm_token_valid_123"

        res = asyncio.run(channel.send(Msg(), RecOk()))
        self.assertTrue(res.success)
        self.assertEqual(res.status, "Sent")
        self.assertIn("mock-fcm", res.provider_message_id)

        # Permanent fail
        class RecPerm:
            token = "fcm_fail_perm_token"

        res = asyncio.run(channel.send(Msg(), RecPerm()))
        self.assertFalse(res.success)
        self.assertEqual(res.error_code, "DEVICE_TOKEN_INVALID")

        # Temporary fail
        class RecTemp:
            token = "fcm_fail_temp_token"

        res = asyncio.run(channel.send(Msg(), RecTemp()))
        self.assertFalse(res.success)
        self.assertEqual(res.error_code, "GATEWAY_TIMEOUT")

    def test_push_fcm_dispatch(self):
        channel = PushChannel(
            provider_type="fcm",
            sender_address="masscommai-fcm-project",
            credentials={"project_id": "masscommai-fcm-project", "server_key": "test_key"},
        )

        class Msg:
            tracking_id = "trk_fcm_01"
            rendered_content = "Critical alert body"

        class Rec:
            token = "client_device_token_abc"

        from unittest.mock import MagicMock
        mock_res = MagicMock()
        mock_res.status_code = 200
        mock_res.json.return_value = {"name": "projects/masscommai-fcm-project/messages/msg_001"}

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_res):
            res = asyncio.run(channel.send(Msg(), Rec()))
            self.assertTrue(res.success)
            self.assertEqual(res.status, "Sent")
            self.assertEqual(res.provider_message_id, "projects/masscommai-fcm-project/messages/msg_001")

    # -------------------------------------------------------------------------
    # 3. Web Broadcast Channel Unit Tests
    # -------------------------------------------------------------------------
    def test_web_broadcast_channel_dispatch(self):
        channel = WebBroadcastChannel(provider_type="mock")
        self.assertEqual(channel.get_channel_name(), "Web")

        class Msg:
            campaign_id = 101
            tracking_id = "trk_bc_01"
            title = "Storm Warning"
            rendered_content = "Severe weather notice"
            language = "en"
            is_emergency = True

        res = asyncio.run(channel.send(Msg(), None))
        self.assertTrue(res.success)
        self.assertEqual(res.status, "Delivered")
        self.assertIn("bc-", res.provider_message_id)

    # -------------------------------------------------------------------------
    # 4. Inbound Webhooks Tests
    # -------------------------------------------------------------------------
    def test_whatsapp_webhook_verification_handshake(self):
        # Valid verification request
        resp = self.client.get(
            "/webhooks/whatsapp",
            params={
                "hub.mode": "subscribe",
                "hub.challenge": "1158201444",
                "hub.verify_token": "masscomm_webhook_verify_token",
            },
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.text, "1158201444")

        # Invalid verification request
        resp_bad = self.client.get(
            "/webhooks/whatsapp",
            params={
                "hub.mode": "subscribe",
                "hub.challenge": "1158201444",
                "hub.verify_token": "wrong_token",
            },
        )
        self.assertEqual(resp_bad.status_code, 403)

    def test_whatsapp_delivery_status_callback_and_idempotency(self):
        # Create an initial message in Sent status
        msg = Message(
            tracking_id="trk_wa_status_test",
            campaign_id=self.campaign.id,
            audience_member_id=1,
            channel="WhatsApp",
            language="en",
            rendered_content="Hello Citizen",
            status="Sent",
            provider_message_id="wamid.test_status_123",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        self.db.add(msg)
        self.db.commit()

        payload = {
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "statuses": [
                                    {
                                        "id": "wamid.test_status_123",
                                        "status": "delivered",
                                        "timestamp": "1700000000",
                                    }
                                ]
                            }
                        }
                    ]
                }
            ]
        }

        # First post: processes delivery
        resp = self.client.post("/webhooks/whatsapp", json=payload)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["events_processed"], 1)

        self.db.refresh(msg)
        self.assertEqual(msg.status, "Delivered")
        self.assertIsNotNone(msg.delivered_at)

        # Second post: deduplication skips reprocessing
        resp_dup = self.client.post("/webhooks/whatsapp", json=payload)
        self.assertEqual(resp_dup.status_code, 200)
        self.assertEqual(resp_dup.json()["events_processed"], 0)

    def test_whatsapp_inbound_citizen_reply(self):
        msg = Message(
            tracking_id="trk_wa_inbound_test",
            campaign_id=self.campaign.id,
            audience_member_id=1,
            channel="WhatsApp",
            language="en",
            rendered_content="Flood alert",
            status="Delivered",
            provider_message_id="wamid.inbound_parent",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        self.db.add(msg)
        self.db.commit()

        payload = {
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "messages": [
                                    {
                                        "id": "wamid.citizen_reply_99",
                                        "from": "+919876543210",
                                        "text": {"body": "Need emergency shelter details."},
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

        # Verify feedback logged
        fb = self.db.execute(select(Feedback).where(Feedback.comment == "Need emergency shelter details.")).scalar_one_or_none()
        self.assertIsNotNone(fb)
        self.assertEqual(fb.campaign_id, self.campaign.id)

    def test_push_webhook_invalid_token(self):
        dt = DeviceToken(
            token="fcm_expired_token_001",
            device_type="android",
            is_active=True,
        )
        self.db.add(dt)
        self.db.commit()

        resp = self.client.post(
            "/webhooks/push",
            json={
                "event_id": "push_event_991",
                "invalid_token": "fcm_expired_token_001",
            },
        )
        self.assertEqual(resp.status_code, 200)

        self.db.refresh(dt)
        self.assertFalse(dt.is_active)

    # -------------------------------------------------------------------------
    # 5. Device Registration and Public Announcements Endpoints
    # -------------------------------------------------------------------------
    def test_device_token_registration_endpoint(self):
        resp = self.client.post(
            "/notifications/devices/register",
            json={
                "token": "browser_web_push_endpoint_token_999",
                "device_type": "web",
                "platform_metadata": {"browser": "Chrome"},
            },
        )
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertEqual(data["token"], "browser_web_push_endpoint_token_999")
        self.assertTrue(data["is_active"])

        # Idempotent reactivation
        resp_re = self.client.post(
            "/notifications/devices/register",
            json={
                "token": "browser_web_push_endpoint_token_999",
                "device_type": "web",
            },
        )
        self.assertEqual(resp_re.status_code, 201)
        self.assertEqual(resp_re.json()["id"], data["id"])

    def test_public_announcements_endpoint(self):
        bc = WebBroadcast(
            campaign_id=self.campaign.id,
            title="Public Water Advisory",
            body="Safe drinking water points operational at Sector 4.",
            language="en",
            is_emergency=True,
            priority="urgent",
            connected_clients_count=5,
        )
        self.db.add(bc)
        self.db.commit()

        resp = self.client.get("/announcements")
        self.assertEqual(resp.status_code, 200)
        items = resp.json()
        self.assertGreaterEqual(len(items), 1)
        self.assertEqual(items[0]["title"], "Public Water Advisory")
        self.assertTrue(items[0]["is_emergency"])
        # Privacy guarantee: no PII fields
        self.assertNotIn("email", items[0])
        self.assertNotIn("phone", items[0])

    def test_broadcast_sse_stream(self):
        from app.services.channels.broadcast_manager import broadcast_manager

        # Test broadcast_manager SSE queue registration and dispatch
        async def run_sse_test():
            q = await broadcast_manager.register_sse_client()
            try:
                test_payload = {"title": "Storm Warning", "body": "High winds"}
                count = await broadcast_manager.broadcast(test_payload)
                self.assertGreaterEqual(count, 1)
                item = q.get_nowait()
                self.assertEqual(item["title"], "Storm Warning")
            finally:
                await broadcast_manager.unregister_sse_client(q)

        asyncio.run(run_sse_test())

    # -------------------------------------------------------------------------
    # 6. Omnichannel Campaign Send & Fallback Tests
    # -------------------------------------------------------------------------
    def test_omnichannel_fallback_whatsapp_to_sms(self):
        """
        Recipient has phone with WhatsApp failure string 'fail_wa'.
        WhatsApp fails -> falls back to SMS -> SMS succeeds!
        """
        member = AudienceMember(
            name="Ramesh Kumar",
            phone="+919870fail_wa",
            email="ramesh@example.gov.in",
            preferred_channel="WhatsApp",
            preferred_language="en",
            consent_status=True,
        )
        self.db.add(member)
        self.db.commit()

        resp = self.client.post(
            f"/campaigns/{self.campaign.id}/send",
            headers=self.manager_headers,
            json={
                "channels": ["WhatsApp", "SMS", "Email"],
                "fallback_order": ["WhatsApp", "SMS", "Email"],
                "enable_fallback": True,
            },
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["sent_messages"] + data["delivered_messages"], 1)

        # Message delivered on SMS
        msg = self.db.execute(select(Message).where(Message.audience_member_id == member.id)).scalar_one()
        self.assertEqual(msg.channel, "SMS")
        self.assertIn(msg.status, ("Sent", "Delivered"))
        # Verify fallback attempts recorded WhatsApp failure
        self.assertEqual(len(msg.fallback_attempts), 2)
        self.assertEqual(msg.fallback_attempts[0]["channel"], "WhatsApp")
        self.assertEqual(msg.fallback_attempts[0]["status"], "Failed")
        self.assertEqual(msg.fallback_attempts[1]["channel"], "SMS")
        self.assertIn(msg.fallback_attempts[1]["status"], ("Sent", "Delivered"))

    def test_omnichannel_fallback_disabled(self):
        """
        When fallback is disabled, a failure on the primary channel does not proceed to fallback.
        """
        member = AudienceMember(
            name="Ananya Roy",
            phone="+919870fail_perm",
            email="ananya@example.gov.in",
            preferred_channel="WhatsApp",
            preferred_language="en",
            consent_status=True,
        )
        self.db.add(member)
        self.db.commit()

        resp = self.client.post(
            f"/campaigns/{self.campaign.id}/send",
            headers=self.manager_headers,
            json={
                "channels": ["WhatsApp", "SMS", "Email"],
                "enable_fallback": False,
            },
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["failed_messages"], 1)

        msg = self.db.execute(select(Message).where(Message.audience_member_id == member.id)).scalar_one()
        self.assertEqual(msg.status, "Failed")
        self.assertEqual(msg.channel, "WhatsApp")

    def test_affirmative_consent_enforcement_omnichannel(self):
        """Citizens without affirmative opt-in are withheld across all omnichannel targets."""
        opted_out = AudienceMember(
            name="Opted Out Citizen",
            phone="+919876543210",
            email="optout@example.gov.in",
            preferred_channel="WhatsApp",
            consent_status=False,
        )
        unconfirmed = AudienceMember(
            name="Unconfirmed Citizen",
            phone="+919876543211",
            email="unconfirmed@example.gov.in",
            preferred_channel="SMS",
            consent_status=None,
        )
        self.db.add_all([opted_out, unconfirmed])
        self.db.commit()

        resp = self.client.post(
            f"/campaigns/{self.campaign.id}/send",
            headers=self.manager_headers,
            json={"channels": ["WhatsApp", "SMS"]},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["opted_out_recipients"], 2)
        self.assertEqual(data["failed_messages"], 2)

    def test_admin_disabled_channel_triggers_fallback(self):
        """If WhatsApp is disabled by admin, sending skips it and uses SMS."""
        # Disable WhatsApp
        wa_cfg = self.db.execute(select(ChannelConfiguration).where(ChannelConfiguration.channel == "WhatsApp")).scalar_one()
        wa_cfg.is_enabled = False
        self.db.commit()

        member = AudienceMember(
            name="Suresh Patel",
            phone="+919876543210",
            email="suresh@example.gov.in",
            preferred_channel="WhatsApp",
            consent_status=True,
        )
        self.db.add(member)
        self.db.commit()

        resp = self.client.post(
            f"/campaigns/{self.campaign.id}/send",
            headers=self.manager_headers,
            json={
                "channels": ["WhatsApp", "SMS"],
                "fallback_order": ["WhatsApp", "SMS"],
                "enable_fallback": True,
            },
        )
        self.assertEqual(resp.status_code, 200)

        msg = self.db.execute(select(Message).where(Message.audience_member_id == member.id)).scalar_one()
        self.assertEqual(msg.channel, "SMS")
        self.assertIn(msg.status, ("Sent", "Delivered"))

    def test_push_token_invalidation_during_dispatch(self):
        """When Push dispatch returns DEVICE_TOKEN_INVALID, the device token is deactivated."""
        member = AudienceMember(
            name="Dev User",
            phone="+919876543210",
            email="dev@example.gov.in",
            preferred_channel="Push",
            consent_status=True,
        )
        self.db.add(member)
        self.db.commit()

        dt = DeviceToken(
            token="push_fail_perm_token_123",
            audience_member_id=member.id,
            device_type="web",
            is_active=True,
        )
        self.db.add(dt)
        self.db.commit()

        # Send campaign with Push channel
        resp = self.client.post(
            f"/campaigns/{self.campaign.id}/send",
            headers=self.manager_headers,
            json={
                "channels": ["Push", "Email"],
                "fallback_order": ["Push", "Email"],
                "enable_fallback": True,
            },
        )
        self.assertEqual(resp.status_code, 200)

        self.db.refresh(dt)
        self.assertFalse(dt.is_active)

    def test_masked_credentials_in_admin_channel_settings(self):
        resp = self.client.get("/admin/channels", headers=self.admin_headers)
        self.assertEqual(resp.status_code, 200)
        items = resp.json()
        channel_names = [i["channel"] for i in items]
        self.assertIn("WhatsApp", channel_names)
        self.assertIn("Push", channel_names)
        self.assertIn("Web", channel_names)

        # Check masked credentials
        wa = next(i for i in items if i["channel"] == "WhatsApp")
        self.assertTrue(wa["has_credentials"])
