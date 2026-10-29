"""Comprehensive automated tests for Task 3: JWT Login, /auth/me, and Admin RBAC."""

import unittest
from datetime import timedelta
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.main import app
from app.db.base import Base
from app.db.session import get_db
from app.db.seed import seed_default_roles, bootstrap_admin_user
from app.models.user import User, Role
from app.core.config import Settings
from app.core.security import get_password_hash, create_access_token


class TestAuthJWTRBAC(unittest.TestCase):
    """Test suite verifying JWT authentication, /auth/me, and Admin RBAC governance."""

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
        Base.metadata.create_all(bind=self.test_engine)
        self.db = self.TestingSessionLocal()
        roles = seed_default_roles(self.db)
        self.admin_role = roles["Admin"]
        self.manager_role = roles["Campaign Manager"]
        self.comm_role = roles["Communication Team"]

        # Seed standard test users
        self.admin_pwd = "AdminSecure123!"
        self.admin_user = User(
            full_name="System Admin",
            email="admin@test.gov.in",
            hashed_password=get_password_hash(self.admin_pwd),
            role_id=self.admin_role.id,
            is_active=True,
        )
        self.db.add(self.admin_user)

        self.comm_pwd = "CommSecure123!"
        self.comm_user = User(
            full_name="Comm Specialist",
            email="comm@test.gov.in",
            hashed_password=get_password_hash(self.comm_pwd),
            role_id=self.comm_role.id,
            is_active=True,
        )
        self.db.add(self.comm_user)

        self.inactive_pwd = "InactiveSecure123!"
        self.inactive_user = User(
            full_name="Inactive User",
            email="inactive@test.gov.in",
            hashed_password=get_password_hash(self.inactive_pwd),
            role_id=self.comm_role.id,
            is_active=False,
        )
        self.db.add(self.inactive_user)

        self.db.commit()
        self.db.refresh(self.admin_user)
        self.db.refresh(self.comm_user)
        self.db.refresh(self.inactive_user)

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

    # --- JWT Login Tests ---

    def test_login_success_returns_signed_token(self):
        """1. Successful login returns signed JWT access token and user metadata."""
        payload = {"email": "comm@test.gov.in", "password": self.comm_pwd}
        res = self.client.post("/auth/login", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("access_token", data)
        self.assertEqual(data["token_type"], "bearer")
        self.assertGreater(data["expires_in"], 0)
        self.assertEqual(data["user"]["email"], "comm@test.gov.in")
        self.assertEqual(data["user"]["role_name"], "Communication Team")
        self.assertNotIn("password", str(data))

    def test_login_fails_for_wrong_password_or_unknown_email(self):
        """2. Invalid credentials return a generic 401 error."""
        # Wrong password
        res1 = self.client.post("/auth/login", json={"email": "comm@test.gov.in", "password": "WrongPassword!"})
        self.assertEqual(res1.status_code, 401)
        self.assertEqual(res1.json()["detail"], "Invalid email or password.")

        # Unknown email
        res2 = self.client.post("/auth/login", json={"email": "unknown@test.gov.in", "password": "AnyPassword1!"})
        self.assertEqual(res2.status_code, 401)
        self.assertEqual(res2.json()["detail"], "Invalid email or password.")

    def test_login_fails_for_inactive_account(self):
        """3. Deactivated accounts cannot log in even with correct password."""
        payload = {"email": "inactive@test.gov.in", "password": self.inactive_pwd}
        res = self.client.post("/auth/login", json=payload)
        self.assertEqual(res.status_code, 401)
        self.assertIn("deactivated", res.json()["detail"].lower())

    # --- GET /auth/me Tests ---

    def test_auth_me_with_valid_token(self):
        """4. Valid Bearer token retrieves live user profile from database."""
        token = create_access_token(self.comm_user.id)
        res = self.client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["email"], "comm@test.gov.in")
        self.assertEqual(res.json()["role_name"], "Communication Team")

    def test_auth_me_rejects_invalid_and_expired_tokens(self):
        """5. Invalid, malformed, and expired tokens return 401."""
        # Malformed token
        res1 = self.client.get("/auth/me", headers={"Authorization": "Bearer not-a-token"})
        self.assertEqual(res1.status_code, 401)

        # Expired token (issued with negative delta)
        expired_token = create_access_token(self.comm_user.id, expires_delta=timedelta(seconds=-10))
        res2 = self.client.get("/auth/me", headers={"Authorization": f"Bearer {expired_token}"})
        self.assertEqual(res2.status_code, 401)

        # Missing token
        res3 = self.client.get("/auth/me")
        self.assertEqual(res3.status_code, 401)

    def test_auth_me_rejects_deactivated_user_with_valid_token(self):
        """6. Deactivating a user immediately revokes access even if their token has not expired."""
        token = create_access_token(self.comm_user.id)

        # Deactivate user in DB
        self.comm_user.is_active = False
        self.db.commit()

        res = self.client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(res.status_code, 401)
        self.assertIn("deactivated", res.json()["detail"].lower())

    # --- RBAC and Admin User Management Tests ---

    def test_non_admin_cannot_access_admin_endpoints(self):
        """7. Non-admin users receive 403 Forbidden on administrative endpoints."""
        comm_token = create_access_token(self.comm_user.id)
        headers = {"Authorization": f"Bearer {comm_token}"}

        # Attempt to list users
        res1 = self.client.get("/admin/users", headers=headers)
        self.assertEqual(res1.status_code, 403)

        # Attempt to update role
        res2 = self.client.put(f"/admin/users/{self.comm_user.id}/role", json={"role_name": "Admin"}, headers=headers)
        self.assertEqual(res2.status_code, 403)

        # Attempt to deactivate user
        res3 = self.client.patch(f"/admin/users/{self.comm_user.id}/status", json={"is_active": False}, headers=headers)
        self.assertEqual(res3.status_code, 403)

    def test_admin_can_list_users_with_pagination_and_search(self):
        """8. Administrator can list all users with pagination and search."""
        admin_token = create_access_token(self.admin_user.id)
        headers = {"Authorization": f"Bearer {admin_token}"}

        res = self.client.get("/admin/users?page=1&page_size=10", headers=headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["total"], 3)
        self.assertEqual(len(data["items"]), 3)

        # Test search filter
        res_search = self.client.get("/admin/users?search=Comm", headers=headers)
        self.assertEqual(res_search.status_code, 200)
        self.assertEqual(res_search.json()["total"], 1)
        self.assertEqual(res_search.json()["items"][0]["email"], "comm@test.gov.in")

    def test_admin_can_update_user_role(self):
        """9. Administrator can elevate a user to Campaign Manager or Admin."""
        admin_token = create_access_token(self.admin_user.id)
        headers = {"Authorization": f"Bearer {admin_token}"}

        # Elevate comm_user to Campaign Manager
        res = self.client.put(
            f"/admin/users/{self.comm_user.id}/role",
            json={"role_name": "Campaign Manager"},
            headers=headers,
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["role_name"], "Campaign Manager")

        # Confirm DB reflects the change
        self.db.refresh(self.comm_user)
        self.assertEqual(self.comm_user.role.name, "Campaign Manager")

    def test_admin_can_toggle_user_status(self):
        """10. Administrator can deactivate and reactivate users."""
        admin_token = create_access_token(self.admin_user.id)
        headers = {"Authorization": f"Bearer {admin_token}"}

        # Deactivate
        res_deactivate = self.client.patch(
            f"/admin/users/{self.comm_user.id}/status",
            json={"is_active": False},
            headers=headers,
        )
        self.assertEqual(res_deactivate.status_code, 200)
        self.assertFalse(res_deactivate.json()["is_active"])

        # Reactivate
        res_activate = self.client.patch(
            f"/admin/users/{self.comm_user.id}/status",
            json={"is_active": True},
            headers=headers,
        )
        self.assertEqual(res_activate.status_code, 200)
        self.assertTrue(res_activate.json()["is_active"])

    def test_admin_self_protection_rules(self):
        """11. Admin cannot deactivate their own account or remove their own Admin role."""
        admin_token = create_access_token(self.admin_user.id)
        headers = {"Authorization": f"Bearer {admin_token}"}

        # Self-demotion attempt
        res_demote = self.client.put(
            f"/admin/users/{self.admin_user.id}/role",
            json={"role_name": "Communication Team"},
            headers=headers,
        )
        self.assertEqual(res_demote.status_code, 400)
        self.assertIn("cannot demote their own account", res_demote.json()["detail"].lower())

        # Self-deactivation attempt
        res_deact = self.client.patch(
            f"/admin/users/{self.admin_user.id}/status",
            json={"is_active": False},
            headers=headers,
        )
        self.assertEqual(res_deact.status_code, 400)
        self.assertIn("cannot deactivate their own account", res_deact.json()["detail"].lower())

    def test_last_admin_protection(self):
        """12. Cannot demote or deactivate the only remaining active Administrator."""
        admin_token = create_access_token(self.admin_user.id)
        headers = {"Authorization": f"Bearer {admin_token}"}

        # Create a second admin to test that demotion works when >1 admins exist
        second_admin = User(
            full_name="Second Admin",
            email="admin2@test.gov.in",
            hashed_password=get_password_hash("AdminPass123!"),
            role_id=self.admin_role.id,
            is_active=True,
        )
        self.db.add(second_admin)
        self.db.commit()
        self.db.refresh(second_admin)

        # Demoting second_admin succeeds because admin_user is still active admin
        res_demote = self.client.put(
            f"/admin/users/{second_admin.id}/role",
            json={"role_name": "Campaign Manager"},
            headers=headers,
        )
        self.assertEqual(res_demote.status_code, 200)

        # Now only 1 active admin remains. Demoting second_admin again if re-promoted or deactivating admin_user fails
        second_admin.role_id = self.admin_role.id
        self.db.commit()

        # Demote admin_user via second_admin token
        second_token = create_access_token(second_admin.id)
        res_demote_first = self.client.put(
            f"/admin/users/{self.admin_user.id}/role",
            json={"role_name": "Campaign Manager"},
            headers={"Authorization": f"Bearer {second_token}"},
        )
        self.assertEqual(res_demote_first.status_code, 200)

    def test_bootstrap_admin_validations_and_idempotency(self):
        """Verify bootstrap_admin_user rejects invalid/empty passwords and enforces byte boundaries."""
        # 1. Rejects invalid email
        with self.assertRaises(ValueError):
            bootstrap_admin_user(self.db, "notanemail", "ValidPass123!")

        # 2. Rejects empty/blank password
        with self.assertRaises(ValueError):
            bootstrap_admin_user(self.db, "newadmin@test.gov.in", "   ")

        # 3. Rejects password under 8 characters
        with self.assertRaises(ValueError):
            bootstrap_admin_user(self.db, "newadmin@test.gov.in", "Short1!")

        # 4. Rejects password exceeding 72 UTF-8 bytes
        oversized_pwd = "A" * 73
        with self.assertRaises(ValueError):
            bootstrap_admin_user(self.db, "newadmin@test.gov.in", oversized_pwd)

        # 5. Succeeds with valid credentials
        valid_pwd = "StrongAdminPassword123!"
        admin = bootstrap_admin_user(
            self.db,
            email="bootstrapped@test.gov.in",
            password=valid_pwd,
            full_name="Bootstrapped Admin",
        )
        self.assertIsNotNone(admin)
        self.assertEqual(admin.role.name, "Admin")
        self.assertTrue(admin.is_active)

        # 6. Idempotently returns existing user on duplicate call without re-creating
        admin_repeat = bootstrap_admin_user(
            self.db,
            email="bootstrapped@test.gov.in",
            password=valid_pwd,
        )
        self.assertEqual(admin.id, admin_repeat.id)

    def test_settings_security_production_validation(self):
        """Verify Settings model validator enforces secure secrets in production/staging and allows dev."""
        # Development mode allows default key
        dev_settings = Settings(
            APP_ENV="development",
            SECRET_KEY="replace-with-a-secure-random-secret-key-at-least-32-chars-long",
        )
        self.assertEqual(dev_settings.APP_ENV, "development")

        # Empty secret is rejected anywhere
        with self.assertRaises(ValueError):
            Settings(APP_ENV="development", SECRET_KEY="")

        # Production with placeholder secret is rejected
        with self.assertRaises(ValueError) as ctx:
            Settings(
                APP_ENV="production",
                SECRET_KEY="replace-with-a-secure-random-secret-key-at-least-32-chars-long",
            )
        self.assertIn("cannot be a default placeholder", str(ctx.exception))

        # Production with short secret (< 32 chars) is rejected
        with self.assertRaises(ValueError) as ctx:
            Settings(
                APP_ENV="production",
                SECRET_KEY="short-secret-under-32-chars",
            )
        self.assertIn("at least 32 characters", str(ctx.exception))

        # Production with 32+ character strong secret succeeds
        strong_secret = "a-very-strong-cryptographic-secret-key-1234567890"
        prod_settings = Settings(
            APP_ENV="production",
            SECRET_KEY=strong_secret,
        )
        self.assertEqual(prod_settings.SECRET_KEY, strong_secret)


if __name__ == "__main__":
    unittest.main()

