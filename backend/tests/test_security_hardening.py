"""Security hardening tests for Task 18.

Validates:
1. Rate limiting enforcement on authentication and AI endpoints (HTTP 429 with Retry-After).
2. Global exception handler sanitization (HTTP 500 without stack trace leaks).
3. PII and credential log redaction (emails, phone numbers, tokens).
4. Production CORS configuration validation.
5. Role-based access control (RBAC) boundaries.
"""

import logging
import unittest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.logging_config import PIIRedactingFilter
from app.core.rate_limiter import reset_rate_limiters, MemoryRateLimiter
from app.main import app
from app.db.base import Base
from app.db.session import get_db
from app.db.seed import seed_default_roles
from app.models.user import User, Role
from app.models.audience import AudienceMember
from app.models.segment import Segment
from app.models.template import Template
from app.models.campaign import Campaign
from app.core.security import get_password_hash, create_access_token


class TestSecurityHardening(unittest.TestCase):
    """Security hardening test suite."""

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

        self.comm_user = User(
            full_name="Communication Officer",
            email="comm.officer@test.gov.in",
            hashed_password=get_password_hash("Password123!"),
            role_id=self.comm_role.id,
            is_active=True,
        )
        self.db.add(self.comm_user)
        self.db.commit()
        self.db.refresh(self.comm_user)

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

    def test_pii_redacting_filter(self):
        """Verify PIIRedactingFilter masks sensitive personal information and credentials."""
        log_filter = PIIRedactingFilter()
        logger = logging.getLogger("test_pii_redactor")
        logger.setLevel(logging.INFO)

        records = []

        class TestHandler(logging.Handler):
            def emit(self, record):
                records.append(record)

        handler = TestHandler()
        handler.addFilter(log_filter)
        logger.addHandler(handler)

        logger.info("Citizen contact email is rajesh.kumar@example.com and mobile is +919811122233.")
        logger.info("Authorization header: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.token123")
        logger.info("Admin password='SecretPassword123' and api_key=\"AIzaSyD-secret-key-456\"")

        assert len(records) == 3
        msg1 = records[0].getMessage()
        assert "rajesh.kumar@example.com" not in msg1
        assert "[EMAIL_REDACTED]" in msg1
        assert "9811122233" not in msg1
        assert "[PHONE_REDACTED]" in msg1

        msg2 = records[1].getMessage()
        assert "eyJhbGci" not in msg2
        assert "Bearer [REDACTED]" in msg2

        msg3 = records[2].getMessage()
        assert "SecretPassword123" not in msg3
        assert "AIzaSyD-secret-key-456" not in msg3
        assert "[REDACTED]" in msg3

    def test_global_unhandled_exception_sanitization(self):
        """Verify unhandled server exceptions do not leak stack traces or internal details."""
        @app.get("/api/v1/test-crash-unhandled-security")
        def route_that_crashes():
            raise RuntimeError("Database connection string postgres://admin:supersecret@10.0.0.1 failed")

        no_raise_client = TestClient(app, raise_server_exceptions=False)
        response = no_raise_client.get("/api/v1/test-crash-unhandled-security")
        assert response.status_code == 500
        data = response.json()
        assert data["error_code"] == "INTERNAL_SERVER_ERROR"
        assert "An internal server error occurred" in data["detail"]
        assert "supersecret" not in response.text
        assert "Traceback" not in response.text

    def test_rate_limiter_memory_sliding_window(self):
        """Test MemoryRateLimiter sliding window tracking directly."""
        limiter = MemoryRateLimiter()
        key = "test_key_direct"
        limit = 3
        window = 5

        # First 3 requests should be allowed
        for _ in range(3):
            allowed, retry_after = limiter.is_allowed(key, limit=limit, window_seconds=window)
            assert allowed is True
            assert retry_after == 0

        # 4th request must be rejected
        allowed, retry_after = limiter.is_allowed(key, limit=limit, window_seconds=window)
        assert allowed is False
        assert retry_after > 0

    def test_auth_login_rate_limiting(self):
        """Verify that excessive login attempts trigger HTTP 429 Too Many Requests."""
        # Rapidly send 12 requests to /auth/login (limit is 10/min)
        statuses = []
        for i in range(12):
            resp = self.client.post(
                "/auth/login",
                json={"email": f"bad_login_{i}@example.com", "password": "WrongPassword123!"},
                headers={"X-Forwarded-For": "192.168.100.50"},
            )
            statuses.append(resp.status_code)

        assert 429 in statuses
        # Test headers and detail
        last_resp = self.client.post(
            "/auth/login",
            json={"email": "bad_login@example.com", "password": "WrongPassword123!"},
            headers={"X-Forwarded-For": "192.168.100.50"},
        )
        assert last_resp.status_code == 429
        assert "Retry-After" in last_resp.headers
        assert "Rate limit exceeded" in last_resp.json()["detail"]

    def test_production_cors_wildcard_rejected(self):
        """Verify that wildcard '*' is rejected in production or staging environments."""
        with self.assertRaises(ValueError):
            Settings(
                APP_ENV="production",
                SECRET_KEY="A" * 32,
                CORS_ORIGINS="http://localhost:5173,*",
            )

    def test_rbac_boundary_comm_team_forbidden_from_admin(self):
        """Verify that a Communication Team user is forbidden (403) from accessing admin routes."""
        token = create_access_token(subject=self.comm_user.id)
        headers = {"Authorization": f"Bearer {token}"}

        # Try to access Admin Users endpoint
        resp = self.client.get("/admin/users", headers=headers)
        assert resp.status_code == 403

        # Try to access Admin Channel settings
        resp2 = self.client.get("/admin/channels", headers=headers)
        assert resp2.status_code == 403

    def test_campaign_preview_pii_masking_sec01(self):
        """SEC-01: Verify campaign preview masks citizen email & phone and validates segment membership."""
        token = create_access_token(subject=self.comm_user.id)
        headers = {"Authorization": f"Bearer {token}"}

        # 1. Seed audience members
        delhi_citizen = AudienceMember(
            name="Sunita Rao",
            email="sunita.rao@example.gov.in",
            phone="+919812345678",
            city="New Delhi",
            state="Delhi",
            preferred_language="hi",
            preferred_channel="email",
            consent_status=True,
        )
        mumbai_citizen = AudienceMember(
            name="Rajesh Patil",
            email="rajesh.patil@example.gov.in",
            phone="+919876501234",
            city="Mumbai",
            state="Maharashtra",
            preferred_language="mr",
            preferred_channel="sms",
            consent_status=True,
        )
        self.db.add_all([delhi_citizen, mumbai_citizen])
        self.db.commit()

        # 2. Seed Delhi segment
        delhi_seg = Segment(
            name="Delhi Residents",
            created_by=self.comm_user.id,
            filter_rules={
                "connector": "AND",
                "conditions": [{"field": "city", "operator": "equals", "value": "New Delhi"}],
            },
        )
        self.db.add(delhi_seg)
        self.db.commit()

        # 3. Seed template and campaign
        template = Template(
            title="Clean City Advisory",
            category="Civic",
            body="Hello {name}, keep {city} clean. Contact {email} or {phone}.",
            created_by=self.comm_user.id,
        )
        self.db.add(template)
        self.db.commit()

        campaign = Campaign(
            name="Clean Delhi Drive",
            campaign_type="Awareness",
            priority="Medium",
            status="Draft",
            channels=["Email", "SMS"],
            created_by=self.comm_user.id,
            template_id=template.id,
        )
        campaign.segments = [delhi_seg]
        self.db.add(campaign)
        self.db.commit()

        # 4. GET /campaigns/{id}/preview with comm team token
        resp = self.client.get(f"/campaigns/{campaign.id}/preview", headers=headers)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        # Requirement 1: Verify PII masking in sample_recipient, rendered_content, and channel previews
        sample = data["sample_recipient"]
        self.assertEqual(sample["name"], "Sunita Rao")
        self.assertEqual(sample["email"], "su***@example.gov.in")
        self.assertEqual(sample["phone"], "+919****5678")
        self.assertNotIn("sunita.rao@example.gov.in", sample["email"])
        self.assertNotIn("+919812345678", sample["phone"])

        rendered = data["rendered_content"]
        self.assertIn("Hello Sunita Rao", rendered)
        self.assertIn("keep New Delhi clean", rendered)
        self.assertIn("su***@example.gov.in", rendered)
        self.assertIn("+919****5678", rendered)
        self.assertNotIn("sunita.rao@example.gov.in", rendered)
        self.assertNotIn("+919812345678", rendered)

        # Check all channel previews
        for ch_name, ch_preview in data["channel_previews"].items():
            self.assertNotIn("sunita.rao@example.gov.in", ch_preview["rendered_body"])
            self.assertNotIn("+919812345678", ch_preview["rendered_body"])

        # Requirement 2: Verify segment scoping across campaigns with multiple linked segments
        mumbai_seg = Segment(
            name="Mumbai Residents",
            created_by=self.comm_user.id,
            filter_rules={
                "connector": "AND",
                "conditions": [{"field": "city", "operator": "equals", "value": "Mumbai"}],
            },
        )
        chennai_citizen = AudienceMember(
            name="Anand Kumar",
            email="anand.kumar@example.gov.in",
            phone="+919844455566",
            city="Chennai",
            state="Tamil Nadu",
            preferred_language="ta",
            preferred_channel="whatsapp",
            consent_status=True,
        )
        self.db.add_all([mumbai_seg, chennai_citizen])
        self.db.commit()

        campaign_multi = Campaign(
            name="Metro Civic Drive",
            campaign_type="Awareness",
            priority="Medium",
            status="Draft",
            channels=["Email", "SMS"],
            created_by=self.comm_user.id,
            template_id=template.id,
        )
        campaign_multi.segments = [delhi_seg, mumbai_seg]
        self.db.add(campaign_multi)
        self.db.commit()

        # Both Delhi and Mumbai citizens match the multi-segment campaign
        resp_delhi = self.client.get(
            f"/campaigns/{campaign_multi.id}/preview?audience_member_id={delhi_citizen.id}",
            headers=headers,
        )
        self.assertEqual(resp_delhi.status_code, 200)
        self.assertEqual(resp_delhi.json()["sample_recipient"]["name"], "Sunita Rao")

        resp_mumbai = self.client.get(
            f"/campaigns/{campaign_multi.id}/preview?audience_member_id={mumbai_citizen.id}",
            headers=headers,
        )
        self.assertEqual(resp_mumbai.status_code, 200)
        self.assertEqual(resp_mumbai.json()["sample_recipient"]["name"], "Rajesh Patil")

        # Chennai citizen matches neither segment -> 400 Bad Request
        resp_chennai = self.client.get(
            f"/campaigns/{campaign_multi.id}/preview?audience_member_id={chennai_citizen.id}",
            headers=headers,
        )
        self.assertEqual(resp_chennai.status_code, 400)
        self.assertIn("does not match any linked campaign segment", resp_chennai.json()["detail"])
        # Ensure error detail never leaks recipient contact information
        self.assertNotIn("anand.kumar@example.gov.in", resp_chennai.text)
        self.assertNotIn("+919844455566", resp_chennai.text)

        # Requirement 3: Unauthorized (unauthenticated) users cannot access recipient info
        unauth_resp = self.client.get(f"/campaigns/{campaign.id}/preview")
        self.assertEqual(unauth_resp.status_code, 401)

        # Single segment scoping rejection (mumbai citizen in delhi-only campaign)
        unmatched_resp = self.client.get(
            f"/campaigns/{campaign.id}/preview?audience_member_id={mumbai_citizen.id}",
            headers=headers,
        )
        self.assertEqual(unmatched_resp.status_code, 400)
        self.assertIn("does not match any linked campaign segment", unmatched_resp.json()["detail"])
        self.assertNotIn("rajesh.patil@example.gov.in", unmatched_resp.text)
        self.assertNotIn("+919876501234", unmatched_resp.text)

        # Requirement 4: Confirm POST preview endpoint enforces identical protections
        # 4a. POST with invalid segment recipient -> 400 Bad Request
        post_unmatched = self.client.post(
            f"/campaigns/{campaign.id}/preview",
            headers=headers,
            json={"audience_member_id": mumbai_citizen.id},
        )
        self.assertEqual(post_unmatched.status_code, 400)
        self.assertIn("does not match any linked campaign segment", post_unmatched.json()["detail"])

        # 4b. POST with valid recipient -> 200 OK with masked PII
        post_matched = self.client.post(
            f"/campaigns/{campaign.id}/preview",
            headers=headers,
            json={"audience_member_id": delhi_citizen.id},
        )
        self.assertEqual(post_matched.status_code, 200)
        post_data = post_matched.json()
        self.assertEqual(post_data["sample_recipient"]["email"], "su***@example.gov.in")
        self.assertEqual(post_data["sample_recipient"]["phone"], "+919****5678")
        self.assertNotIn("sunita.rao@example.gov.in", post_data["rendered_content"])

        # Requirement 5: Confirm custom placeholder substitution remains functional in POST
        post_custom = self.client.post(
            f"/campaigns/{campaign.id}/preview",
            headers=headers,
            json={
                "audience_member_id": delhi_citizen.id,
                "custom_placeholders": {
                    "{name}": "Chief Health Officer",
                    "{email}": "helpline@health.gov.in",
                },
            },
        )
        self.assertEqual(post_custom.status_code, 200)
        custom_data = post_custom.json()
        self.assertIn("Hello Chief Health Officer", custom_data["rendered_content"])
        self.assertIn("helpline@health.gov.in", custom_data["rendered_content"])
