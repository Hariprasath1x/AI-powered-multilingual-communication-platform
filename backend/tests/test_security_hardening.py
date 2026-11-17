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
