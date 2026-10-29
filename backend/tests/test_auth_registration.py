"""Focused automated unit and integration tests for Task 2 User Registration & Role Seeding."""

import unittest
from unittest.mock import patch
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.exc import OperationalError
from fastapi.testclient import TestClient

from app.main import app
from app.db.base import Base
from app.db.session import get_db
from app.db.seed import seed_default_roles
from app.models.user import User, Role
from app.core.security import verify_password


class TestUserRegistrationAndRoleSeeding(unittest.TestCase):
    """Test suite verifying registration rules, bcrypt 72-byte limit, and strict role security."""

    @classmethod
    def setUpClass(cls):
        # Isolated in-memory SQLite database for test execution
        cls.test_engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        cls.TestingSessionLocal = sessionmaker(
            autocommit=False, autoflush=False, bind=cls.test_engine
        )

    def setUp(self):
        # Create schema freshly for each test
        Base.metadata.create_all(bind=self.test_engine)
        self.db = self.TestingSessionLocal()
        seed_default_roles(self.db)

        # Override get_db dependency in FastAPI app
        def override_get_db():
            try:
                yield self.db
            finally:
                pass

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(bind=self.test_engine)
        app.dependency_overrides.clear()

    def test_1_valid_registration_assigns_communication_team(self):
        """1. A valid registration creates one user, assigns Communication Team, and returns HTTP 201."""
        payload = {
            "name": "Aarav Patel",
            "email": "aarav.patel@disastermgmt.gov.in",
            "phone": "+919876543210",
            "organization": "State Disaster Management Authority",
            "password": "StrongPassword123!",
        }
        response = self.client.post("/auth/register", json=payload)
        self.assertEqual(response.status_code, 201)
        data = response.json()

        self.assertEqual(data["status"], "success")
        self.assertEqual(data["user"]["full_name"], "Aarav Patel")
        self.assertEqual(data["user"]["email"], "aarav.patel@disastermgmt.gov.in")
        self.assertEqual(data["user"]["role_name"], "Communication Team")
        self.assertTrue(data["user"]["is_active"])
        self.assertIn("id", data["user"])
        self.assertNotIn("password", data["user"])
        self.assertNotIn("hashed_password", data["user"])

        # Verify exactly one record in the database with Communication Team role
        user = self.db.execute(select(User)).scalar_one()
        self.assertEqual(user.role.name, "Communication Team")

    def test_2_campaign_manager_request_is_rejected(self):
        """2. Supplying role_request: 'Campaign Manager' is rejected with 422 and cannot grant that role."""
        payload = {
            "name": "Unauthorized Manager",
            "email": "manager.attempt@gov.in",
            "password": "SecurePassword123!",
            "role_request": "Campaign Manager",
        }
        response = self.client.post("/auth/register", json=payload)
        self.assertEqual(response.status_code, 422)
        self.assertIn("Communication Team", response.text)

        # Confirm no user account was created
        user = self.db.execute(select(User).where(User.email == "manager.attempt@gov.in")).scalar_one_or_none()
        self.assertIsNone(user)

    def test_3_client_role_tampering_is_rejected(self):
        """3. Supplying 'role', 'role_id', or 'role_name' cannot elevate permissions and is rejected."""
        # Attempt A: Explicit 'role: Admin'
        payload_role = {
            "name": "Hacker A",
            "email": "hacker.a@test.com",
            "password": "SecurePassword123!",
            "role": "Admin",
        }
        res_a = self.client.post("/auth/register", json=payload_role)
        self.assertEqual(res_a.status_code, 422)
        self.assertIn("role", res_a.text)

        # Attempt B: Privileged 'role_id: 1'
        payload_role_id = {
            "name": "Hacker B",
            "email": "hacker.b@test.com",
            "password": "SecurePassword123!",
            "role_id": 1,
        }
        res_b = self.client.post("/auth/register", json=payload_role_id)
        self.assertEqual(res_b.status_code, 422)
        self.assertIn("role_id", res_b.text)

        # Attempt C: role_request 'Admin'
        payload_admin_req = {
            "name": "Hacker C",
            "email": "hacker.c@test.com",
            "password": "SecurePassword123!",
            "role_request": "Admin",
        }
        res_c = self.client.post("/auth/register", json=payload_admin_req)
        self.assertEqual(res_c.status_code, 422)

        # Confirm zero users were created from malicious payloads
        users = self.db.execute(select(User)).scalars().all()
        self.assertEqual(len(users), 0)

    def test_4_ascii_password_exceeding_72_bytes_returns_422(self):
        """4. An ASCII password exceeding 72 bytes returns HTTP 422, not HTTP 500."""
        oversized_ascii = "A1" + ("x" * 75)  # 77 bytes
        self.assertGreater(len(oversized_ascii.encode("utf-8")), 72)

        payload = {
            "name": "Long Password User",
            "email": "long.pwd@test.com",
            "password": oversized_ascii,
        }
        response = self.client.post("/auth/register", json=payload)
        self.assertEqual(response.status_code, 422)
        self.assertIn("72 bytes", response.text)

        # Confirm no user was created
        user = self.db.execute(select(User).where(User.email == "long.pwd@test.com")).scalar_one_or_none()
        self.assertIsNone(user)

    def test_5_multibyte_password_exceeding_72_bytes_returns_422(self):
        """5. A multibyte UTF-8 password exceeding 72 bytes returns HTTP 422, not HTTP 500."""
        # 5 ASCII chars (5 bytes) + 4 Devanagari words (24 chars * 3 bytes = 72 bytes) = 77 bytes total
        multibyte_oversized = "Pass1" + ("नमस्ते" * 4)
        self.assertGreater(len(multibyte_oversized.encode("utf-8")), 72)
        self.assertLessEqual(len(multibyte_oversized), 128)  # passes character length but exceeds byte length

        payload = {
            "name": "Hindi Long User",
            "email": "hindi.long@test.com",
            "password": multibyte_oversized,
        }
        response = self.client.post("/auth/register", json=payload)
        self.assertEqual(response.status_code, 422)
        self.assertIn("72 bytes", response.text)

    def test_6_valid_multibyte_password_within_72_bytes_succeeds(self):
        """6. A valid multibyte password within 72 bytes registers and verifies correctly."""
        # 5 ASCII chars (5 bytes) + 2 Devanagari words (12 chars * 3 bytes = 36 bytes) = 41 bytes total
        multibyte_valid = "Pass1" + ("नमस्ते" * 2)
        self.assertLessEqual(len(multibyte_valid.encode("utf-8")), 72)

        payload = {
            "name": "Hindi Valid User",
            "email": "hindi.valid@test.com",
            "password": multibyte_valid,
        }
        response = self.client.post("/auth/register", json=payload)
        self.assertEqual(response.status_code, 201)

        # Inspect database and verify bcrypt password verification
        user = self.db.execute(select(User).where(User.email == "hindi.valid@test.com")).scalar_one()
        self.assertTrue(verify_password(multibyte_valid, user.hashed_password))
        self.assertFalse(verify_password("WrongPassword123!", user.hashed_password))

    def test_7_password_hashing_and_secrecy(self):
        """7. Passwords are stored as bcrypt hashes and never exposed in responses or plaintext."""
        raw_password = "SecurePassword2026!"
        payload = {
            "full_name": "Divya Krishnan",
            "email": "divya.k@health.gov.in",
            "password": raw_password,
        }
        response = self.client.post("/auth/register", json=payload)
        self.assertEqual(response.status_code, 201)
        body = response.json()

        self.assertNotIn("password", str(body))
        self.assertNotIn("hashed_password", str(body))

        user = self.db.execute(select(User).where(User.email == "divya.k@health.gov.in")).scalar_one()
        self.assertNotEqual(user.hashed_password, raw_password)
        self.assertTrue(user.hashed_password.startswith("$2b$") or user.hashed_password.startswith("$2a$"))
        self.assertTrue(verify_password(raw_password, user.hashed_password))

    def test_8_email_normalization(self):
        """8. Email normalization strips whitespace and converts to lowercase consistently."""
        payload = {
            "full_name": "Kavita Rao",
            "email": "   Kavita.Rao@Education.GOV.In   ",
            "password": "Password123!",
        }
        response = self.client.post("/auth/register", json=payload)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["user"]["email"], "kavita.rao@education.gov.in")

        user = self.db.execute(select(User).where(User.email == "kavita.rao@education.gov.in")).scalar_one()
        self.assertEqual(user.email, "kavita.rao@education.gov.in")

    def test_9_duplicate_email_rejected_with_409(self):
        """9. Duplicate email registration is rejected gracefully with HTTP 409 Conflict."""
        payload1 = {
            "full_name": "Rohan Sen",
            "email": "rohan.sen@municipality.gov.in",
            "password": "Password123!",
        }
        res1 = self.client.post("/auth/register", json=payload1)
        self.assertEqual(res1.status_code, 201)

        payload2 = {
            "full_name": "Another Rohan",
            "email": "ROHAN.SEN@MUNICIPALITY.GOV.IN",
            "password": "DifferentPassword123!",
        }
        res2 = self.client.post("/auth/register", json=payload2)
        self.assertEqual(res2.status_code, 409)
        self.assertIn("already exists", res2.json()["detail"])

    def test_10_default_role_seeding_is_idempotent(self):
        """10. Default role seeding can run repeatedly without creating duplicates."""
        initial_roles = self.db.execute(select(Role)).scalars().all()
        self.assertEqual(len(initial_roles), 3)

        seed_default_roles(self.db)
        seed_default_roles(self.db)

        subsequent_roles = self.db.execute(select(Role)).scalars().all()
        self.assertEqual(len(subsequent_roles), 3)

    def test_11_database_errors_rollback_cleanly(self):
        """11. Database commit failures roll back cleanly and return HTTP 500 without orphan records."""
        payload = {
            "full_name": "Error User",
            "email": "error.user@test.com",
            "password": "Password123!",
        }
        with patch.object(self.db, "commit", side_effect=OperationalError("disk full", {}, None)):
            response = self.client.post("/auth/register", json=payload)
            self.assertEqual(response.status_code, 500)

        user = self.db.execute(select(User).where(User.email == "error.user@test.com")).scalar_one_or_none()
        self.assertIsNone(user)


if __name__ == "__main__":
    unittest.main()
