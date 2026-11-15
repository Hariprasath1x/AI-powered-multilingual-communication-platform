"""Comprehensive HTTP integration test suite for Task 8, Checkpoint 2: Content Quality APIs."""

import unittest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.main import app
from app.db.base import Base
from app.db.session import get_db
from app.db.seed import seed_default_roles
from app.models.user import User
from app.models.content_asset import ContentAsset
from app.core.security import get_password_hash, create_access_token


class TestQualityAPI(unittest.TestCase):
    """Integration test suite covering Quality Assessment endpoints, RBAC, staleness, and approval blocking."""

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

        self.admin_user = User(
            full_name="Admin Director",
            email="admin.director@agency.gov.in",
            hashed_password=get_password_hash("AdminSecret123!"),
            role_id=self.admin_role.id,
            is_active=True,
        )
        self.manager_user = User(
            full_name="Manager Alpha",
            email="manager.alpha@agency.gov.in",
            hashed_password=get_password_hash("ManagerPass123!"),
            role_id=self.manager_role.id,
            is_active=True,
        )
        self.comm_user = User(
            full_name="Comm Specialist",
            email="comm.specialist@agency.gov.in",
            hashed_password=get_password_hash("CommPass123!"),
            role_id=self.comm_role.id,
            is_active=True,
        )
        self.db.add_all([self.admin_user, self.manager_user, self.comm_user])
        self.db.commit()

        # Seed sample ContentAsset for testing
        self.asset = ContentAsset(
            title="Monsoon Safety Protocols",
            body="Dear {name}, please adhere to municipal monsoon flood advisories in {city}.",
            summary="Monsoon notice",
            call_to_action="Visit municipal portal",
            category="Disaster Preparedness",
            tone="informative",
            channel="SMS",
            source_language="en",
            operation_type="generation",
            review_status="Draft",
            created_by=self.manager_user.id,
        )
        self.db.add(self.asset)
        self.db.commit()
        self.db.refresh(self.asset)

        # Access Tokens
        self.admin_token = create_access_token(self.admin_user.id)
        self.manager_token = create_access_token(self.manager_user.id)
        self.comm_token = create_access_token(self.comm_user.id)

        # FastApi Test Client dependency override
        def override_get_db():
            db = self.TestingSessionLocal()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(bind=self.test_engine)
        app.dependency_overrides.clear()

    def _headers(self, token: str) -> dict:
        return {"Authorization": f"Bearer {token}"}

    # -------------------------------------------------------------
    # 1. Unauthenticated & Authorization Rejections
    # -------------------------------------------------------------

    def test_unauthenticated_requests_rejected(self):
        """Unauthenticated requests return 401."""
        res_eval = self.client.post(f"/content/{self.asset.id}/evaluate")
        self.assertEqual(res_eval.status_code, 401)

        res_qual = self.client.get(f"/content/{self.asset.id}/quality")
        self.assertEqual(res_qual.status_code, 401)

        res_ready = self.client.get(f"/content/{self.asset.id}/editorial-readiness")
        self.assertEqual(res_ready.status_code, 401)

    def test_rbac_evaluation_and_decision_permissions(self):
        """Comm Team cannot evaluate or patch finding decisions; can read quality report."""
        # Comm Team evaluate attempt -> 403 Forbidden
        res_eval = self.client.post(
            f"/content/{self.asset.id}/evaluate",
            headers=self._headers(self.comm_token),
        )
        self.assertEqual(res_eval.status_code, 403)

        # Manager can evaluate
        res_eval_mgr = self.client.post(
            f"/content/{self.asset.id}/evaluate",
            headers=self._headers(self.manager_token),
        )
        self.assertEqual(res_eval_mgr.status_code, 200)

        # Comm Team can read assessment
        res_get_comm = self.client.get(
            f"/content/{self.asset.id}/quality",
            headers=self._headers(self.comm_token),
        )
        self.assertEqual(res_get_comm.status_code, 200)
        self.assertIsNotNone(res_get_comm.json())

    # -------------------------------------------------------------
    # 2. Quality Evaluation & Score Calculation
    # -------------------------------------------------------------

    def test_evaluate_content_creates_assessment_and_scores(self):
        """Evaluating content returns overall score, dimension breakdown, and categorized findings."""
        res = self.client.post(
            f"/content/{self.asset.id}/evaluate",
            json={"provider_type": "mock"},
            headers=self._headers(self.manager_token),
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()

        self.assertEqual(data["content_asset_id"], self.asset.id)
        self.assertFalse(data["is_outdated"])
        self.assertGreaterEqual(data["overall_score"], 70.0)
        self.assertIn("language_grammar", data["dimension_scores"])
        self.assertIn("channel_compliance", data["dimension_scores"])

        # Query latest quality endpoint
        res_latest = self.client.get(
            f"/content/{self.asset.id}/quality",
            headers=self._headers(self.manager_token),
        )
        self.assertEqual(res_latest.status_code, 200)
        latest_data = res_latest.json()
        self.assertEqual(latest_data["id"], data["id"])

    # -------------------------------------------------------------
    # 3. Staleness Detection After Content Edits
    # -------------------------------------------------------------

    def test_content_edit_invalidates_previous_assessment(self):
        """Modifying content copy flags existing assessment as outdated."""
        # 1. Run evaluation
        self.client.post(
            f"/content/{self.asset.id}/evaluate",
            json={"provider_type": "mock"},
            headers=self._headers(self.manager_token),
        )

        # Verify initial assessment is fresh
        res_qual = self.client.get(f"/content/{self.asset.id}/quality", headers=self._headers(self.manager_token))
        self.assertFalse(res_qual.json()["is_outdated"])

        # 2. Edit content body
        res_edit = self.client.put(
            f"/content/{self.asset.id}",
            json={"body": "Modified body content after assessment was conducted."},
            headers=self._headers(self.manager_token),
        )
        self.assertEqual(res_edit.status_code, 200)

        # 3. Query quality assessment -> is_outdated must now be True!
        res_qual_after = self.client.get(f"/content/{self.asset.id}/quality", headers=self._headers(self.manager_token))
        self.assertTrue(res_qual_after.json()["is_outdated"])
        self.assertEqual(res_qual_after.json()["status"], "outdated")

        # 4. Check editorial readiness -> approval is blocked due to outdated assessment
        res_ready = self.client.get(f"/content/{self.asset.id}/editorial-readiness", headers=self._headers(self.manager_token))
        ready_data = res_ready.json()
        self.assertTrue(ready_data["is_outdated"])
        self.assertTrue(ready_data["is_approval_blocked"])
        self.assertEqual(ready_data["readiness_status"], "Evaluation Outdated")

    # -------------------------------------------------------------
    # 4. Finding Decision Workflow & Approval Blocker
    # -------------------------------------------------------------

    def test_critical_finding_blocks_approval_until_resolved(self):
        """Unresolved critical finding blocks transition to Approved; resolving allows approval."""
        # Create an asset with malformed placeholder
        bad_asset = ContentAsset(
            title="Emergency Notice",
            body="Citizen {name, urgent alert in {city}.",
            category="Disaster Preparedness",
            tone="urgent",
            channel="SMS",
            source_language="en",
            review_status="Draft",
            created_by=self.manager_user.id,
        )
        self.db.add(bad_asset)
        self.db.commit()
        self.db.refresh(bad_asset)

        # 1. Run evaluation -> triggers CRITICAL finding (RULE-PH-001)
        res_eval = self.client.post(
            f"/content/{bad_asset.id}/evaluate",
            json={"provider_type": "mock"},
            headers=self._headers(self.manager_token),
        )
        self.assertEqual(res_eval.status_code, 200)
        data = res_eval.json()
        self.assertGreaterEqual(data["critical_issues_count"], 1)

        crit_findings = [f for f in data["findings"] if f["severity"] == "critical"]
        self.assertTrue(len(crit_findings) >= 1)
        finding_id = crit_findings[0]["id"]

        # Move status to In Review first
        res_in_review = self.client.patch(
            f"/content/{bad_asset.id}/review",
            json={"review_status": "In Review"},
            headers=self._headers(self.manager_token),
        )
        self.assertEqual(res_in_review.status_code, 200)

        # 2. Attempt to Approve -> MUST FAIL with 400 because critical finding is pending!
        res_approve_fail = self.client.patch(
            f"/content/{bad_asset.id}/review",
            json={"review_status": "Approved", "review_notes": "Attempting bypass"},
            headers=self._headers(self.admin_token),
        )
        self.assertEqual(res_approve_fail.status_code, 400)
        self.assertIn("critical", res_approve_fail.json()["detail"].lower())

        # 3. Resolve the finding: Record reviewer decision
        res_patch_finding = self.client.patch(
            f"/content/{bad_asset.id}/quality/findings/{finding_id}",
            json={
                "reviewer_decision": "corrected",
                "decision_notes": "Corrected closing brace in copy.",
            },
            headers=self._headers(self.manager_token),
        )
        self.assertEqual(res_patch_finding.status_code, 200)
        self.assertEqual(res_patch_finding.json()["reviewer_decision"], "corrected")

        # 4. Check editorial readiness -> approval is now unblocked
        res_ready = self.client.get(
            f"/content/{bad_asset.id}/editorial-readiness",
            headers=self._headers(self.manager_token),
        )
        self.assertFalse(res_ready.json()["is_approval_blocked"])
        self.assertEqual(res_ready.json()["critical_unresolved_count"], 0)

        # 5. Attempt Approval again -> SUCCEEDS!
        res_approve_success = self.client.patch(
            f"/content/{bad_asset.id}/review",
            json={"review_status": "Approved", "review_notes": "Approved after correction"},
            headers=self._headers(self.admin_token),
        )
        self.assertEqual(res_approve_success.status_code, 200)
        self.assertEqual(res_approve_success.json()["review_status"], "Approved")

    # -------------------------------------------------------------
    # 5. Assessment History
    # -------------------------------------------------------------

    def test_assessment_history_preserves_audit_trail(self):
        """Multiple evaluations are preserved chronologically in quality history."""
        # Evaluation 1
        self.client.post(
            f"/content/{self.asset.id}/evaluate",
            json={"provider_type": "mock"},
            headers=self._headers(self.manager_token),
        )
        # Evaluation 2
        self.client.post(
            f"/content/{self.asset.id}/evaluate",
            json={"provider_type": "mock"},
            headers=self._headers(self.manager_token),
        )

        res_history = self.client.get(
            f"/content/{self.asset.id}/quality/history",
            headers=self._headers(self.manager_token),
        )
        self.assertEqual(res_history.status_code, 200)
        history = res_history.json()
        self.assertEqual(len(history), 2)
        # Verify ordered newest first
        self.assertGreaterEqual(history[0]["id"], history[1]["id"])


if __name__ == "__main__":
    unittest.main()

