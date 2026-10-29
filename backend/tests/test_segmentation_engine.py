"""Comprehensive test suite for Task 5: Audience Segmentation Engine & Visual Rule Builder."""

import unittest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.main import app
from app.db.base import Base
from app.db.session import get_db
from app.db.seed import seed_default_roles
from app.models.user import User
from app.models.segment import Segment
from app.models.audience import AudienceMember
from app.core.security import get_password_hash, create_access_token
from app.schemas.segment import (
    SUPPORTED_SEGMENT_FIELDS,
    RuleCondition,
    RuleGroup,
    SegmentCreate,
    SegmentPreviewRequest,
)
from app.services.segment_service import (
    compile_rule_condition,
    compile_rule_group,
    preview_rules,
    create_segment,
    update_segment,
    delete_segment,
)


class TestSegmentationEngine(unittest.TestCase):
    """Test suite covering rule compilation, schema validation, RBAC, ownership, and preview APIs."""

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

        # 1. Admin User
        self.admin_user = User(
            full_name="Admin Director",
            email="admin.director@agency.gov.in",
            hashed_password=get_password_hash("AdminPass123!"),
            role_id=self.admin_role.id,
            is_active=True,
        )
        self.db.add(self.admin_user)

        # 2. Campaign Manager A (Lead)
        self.manager_user = User(
            full_name="Manager Lead A",
            email="manager.a@agency.gov.in",
            hashed_password=get_password_hash("ManagerPass123!"),
            role_id=self.manager_role.id,
            is_active=True,
        )
        self.db.add(self.manager_user)

        # 3. Campaign Manager B (Other Lead)
        self.other_manager = User(
            full_name="Manager Lead B",
            email="manager.b@agency.gov.in",
            hashed_password=get_password_hash("ManagerBPass123!"),
            role_id=self.manager_role.id,
            is_active=True,
        )
        self.db.add(self.other_manager)

        # 4. Communication Team User
        self.comm_user = User(
            full_name="Comm Specialist",
            email="comm.specialist@agency.gov.in",
            hashed_password=get_password_hash("CommPass123!"),
            role_id=self.comm_role.id,
            is_active=True,
        )
        self.db.add(self.comm_user)

        # Seed diverse audience members for segment testing
        # 1. Hindi elderly, confirmed consent, email
        self.db.add(AudienceMember(
            name="Aarav Sharma",
            email="aarav.sharma@example.gov.in",
            phone="+919876543210",
            age=65,
            gender="Male",
            city="New Delhi",
            state="Delhi",
            preferred_language="hi",
            preferred_channel="email",
            occupation="Retired",
            consent_status=True,
        ))
        # 2. Hindi youth, unconfirmed consent, sms
        self.db.add(AudienceMember(
            name="Priya Verma",
            email="priya.verma@example.gov.in",
            phone="+919876543211",
            age=24,
            gender="Female",
            city="Varanasi",
            state="Uttar Pradesh",
            preferred_language="hi",
            preferred_channel="sms",
            occupation="Student",
            consent_status=None,
        ))
        # 3. Tamil middle-aged, confirmed consent, whatsapp
        self.db.add(AudienceMember(
            name="Karthik Raman",
            email="karthik.raman@example.gov.in",
            phone="+919876543212",
            age=42,
            gender="Male",
            city="Chennai",
            state="Tamil Nadu",
            preferred_language="ta",
            preferred_channel="whatsapp",
            occupation="Engineer",
            consent_status=True,
        ))
        # 4. Bengali middle-aged, revoked consent, email
        self.db.add(AudienceMember(
            name="Ananya Sen",
            email="ananya.sen@example.gov.in",
            phone=None,
            age=38,
            gender="Female",
            city="Kolkata",
            state="West Bengal",
            preferred_language="bn",
            preferred_channel="email",
            occupation="Teacher",
            consent_status=False,
        ))
        # 5. English elderly, unconfirmed consent, voice
        self.db.add(AudienceMember(
            name="Robert Dsouza",
            email="robert.dsouza@example.gov.in",
            phone="+919876543214",
            age=70,
            gender="Male",
            city="Panaji",
            state="Goa",
            preferred_language="en",
            preferred_channel="voice",
            occupation="Retired",
            consent_status=None,
        ))

        self.db.commit()
        self.db.refresh(self.admin_user)
        self.db.refresh(self.manager_user)
        self.db.refresh(self.other_manager)
        self.db.refresh(self.comm_user)

        self.admin_token = create_access_token(self.admin_user.id)
        self.manager_token = create_access_token(self.manager_user.id)
        self.other_manager_token = create_access_token(self.other_manager.id)
        self.comm_token = create_access_token(self.comm_user.id)

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

    # =========================================================================
    # 1. Rule Compiler & Execution Unit Tests
    # =========================================================================

    def test_compile_rule_condition_numeric(self):
        """Test numeric comparisons on age field."""
        cond_gt = RuleCondition(field="age", operator="greater_than", value=50)
        expr_gt = compile_rule_condition(cond_gt)
        matches = self.db.execute(select(AudienceMember).where(expr_gt)).scalars().all()
        # Ages > 50 are Aarav (65) and Robert (70)
        self.assertEqual(len(matches), 2)
        names = {m.name for m in matches}
        self.assertIn("Aarav Sharma", names)
        self.assertIn("Robert Dsouza", names)

        cond_lte = RuleCondition(field="age", operator="less_than_or_equal", value=42)
        expr_lte = compile_rule_condition(cond_lte)
        matches_lte = self.db.execute(select(AudienceMember).where(expr_lte)).scalars().all()
        # Ages <= 42 are Priya (24), Karthik (42), Ananya (38)
        self.assertEqual(len(matches_lte), 3)

    def test_compile_rule_condition_text_and_contains(self):
        """Test text contains, starts_with, and equals operators."""
        cond_contains = RuleCondition(field="city", operator="contains", value="delhi")
        expr = compile_rule_condition(cond_contains)
        matches = self.db.execute(select(AudienceMember).where(expr)).scalars().all()
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].name, "Aarav Sharma")

        cond_starts = RuleCondition(field="state", operator="starts_with", value="tamil")
        expr_starts = compile_rule_condition(cond_starts)
        matches_starts = self.db.execute(select(AudienceMember).where(expr_starts)).scalars().all()
        self.assertEqual(len(matches_starts), 1)
        self.assertEqual(matches_starts[0].name, "Karthik Raman")

    def test_compile_rule_condition_categorical_in(self):
        """Test categorical 'in' operator with list of values."""
        cond_in = RuleCondition(field="preferred_language", operator="in", value=["hi", "ta"])
        expr = compile_rule_condition(cond_in)
        matches = self.db.execute(select(AudienceMember).where(expr)).scalars().all()
        # Hindi (Aarav, Priya) + Tamil (Karthik) = 3
        self.assertEqual(len(matches), 3)

    def test_compile_rule_condition_unary_null_checks(self):
        """Test is_empty and is_not_empty operators."""
        cond_empty_phone = RuleCondition(field="phone", operator="is_empty")
        expr_empty = compile_rule_condition(cond_empty_phone)
        matches_empty = self.db.execute(select(AudienceMember).where(expr_empty)).scalars().all()
        # Only Ananya Sen has phone=None
        self.assertEqual(len(matches_empty), 1)
        self.assertEqual(matches_empty[0].name, "Ananya Sen")

        cond_not_empty_phone = RuleCondition(field="phone", operator="is_not_empty")
        expr_not_empty = compile_rule_condition(cond_not_empty_phone)
        matches_not_empty = self.db.execute(select(AudienceMember).where(expr_not_empty)).scalars().all()
        self.assertEqual(len(matches_not_empty), 4)

    def test_compile_rule_condition_tri_state_consent(self):
        """Test tri-state consent filtering: True, False, and None."""
        # Confirmed consent: True
        cond_true = RuleCondition(field="consent_status", operator="equals", value=True)
        matches_true = self.db.execute(select(AudienceMember).where(compile_rule_condition(cond_true))).scalars().all()
        self.assertEqual(len(matches_true), 2)  # Aarav and Karthik

        # Revoked consent: False
        cond_false = RuleCondition(field="consent_status", operator="equals", value=False)
        matches_false = self.db.execute(select(AudienceMember).where(compile_rule_condition(cond_false))).scalars().all()
        self.assertEqual(len(matches_false), 1)  # Ananya
        self.assertEqual(matches_false[0].name, "Ananya Sen")

        # Unconfirmed consent: None / null
        cond_null = RuleCondition(field="consent_status", operator="equals", value=None)
        matches_null = self.db.execute(select(AudienceMember).where(compile_rule_condition(cond_null))).scalars().all()
        self.assertEqual(len(matches_null), 2)  # Priya and Robert

    def test_compile_rule_group_and_or_logic(self):
        """Test AND and OR rule groups and nested precedence."""
        # AND: preferred_language == 'hi' AND age >= 60 -> Aarav Sharma
        group_and = RuleGroup(
            connector="AND",
            conditions=[
                RuleCondition(field="preferred_language", operator="equals", value="hi"),
                RuleCondition(field="age", operator="greater_than_or_equal", value=60),
            ]
        )
        expr_and = compile_rule_group(group_and)
        matches_and = self.db.execute(select(AudienceMember).where(expr_and)).scalars().all()
        self.assertEqual(len(matches_and), 1)
        self.assertEqual(matches_and[0].name, "Aarav Sharma")

        # OR: preferred_channel == 'whatsapp' OR preferred_channel == 'voice' -> Karthik, Robert
        group_or = RuleGroup(
            connector="OR",
            conditions=[
                RuleCondition(field="preferred_channel", operator="equals", value="whatsapp"),
                RuleCondition(field="preferred_channel", operator="equals", value="voice"),
            ]
        )
        expr_or = compile_rule_group(group_or)
        matches_or = self.db.execute(select(AudienceMember).where(expr_or)).scalars().all()
        self.assertEqual(len(matches_or), 2)

        # Nested Group: (preferred_language == 'hi' AND age < 30) OR (preferred_language == 'ta' AND age >= 40)
        # Priya (hi, 24) and Karthik (ta, 42)
        group_nested = RuleGroup(
            connector="OR",
            groups=[
                RuleGroup(
                    connector="AND",
                    conditions=[
                        RuleCondition(field="preferred_language", operator="equals", value="hi"),
                        RuleCondition(field="age", operator="less_than", value=30),
                    ]
                ),
                RuleGroup(
                    connector="AND",
                    conditions=[
                        RuleCondition(field="preferred_language", operator="equals", value="ta"),
                        RuleCondition(field="age", operator="greater_than_or_equal", value=40),
                    ]
                ),
            ]
        )
        expr_nested = compile_rule_group(group_nested)
        matches_nested = self.db.execute(select(AudienceMember).where(expr_nested)).scalars().all()
        self.assertEqual(len(matches_nested), 2)
        names = {m.name for m in matches_nested}
        self.assertEqual(names, {"Priya Verma", "Karthik Raman"})

    # =========================================================================
    # 2. Schema Validation Tests
    # =========================================================================

    def test_schema_rejects_unsupported_field(self):
        """Reject fields not present in SUPPORTED_SEGMENT_FIELDS allowlist."""
        with self.assertRaises(ValueError):
            RuleCondition(field="credit_score", operator="equals", value=750)

    def test_schema_rejects_invalid_operator_for_field(self):
        """Reject numeric operators on text fields."""
        with self.assertRaises(ValueError):
            RuleCondition(field="name", operator="greater_than", value="John")

    def test_schema_rejects_out_of_bounds_age(self):
        """Reject age outside 1-120 range."""
        with self.assertRaises(ValueError):
            RuleCondition(field="age", operator="equals", value=150)
        with self.assertRaises(ValueError):
            RuleCondition(field="age", operator="equals", value=0)

    def test_schema_rejects_excessive_conditions(self):
        """Reject rule groups with more than 20 conditions."""
        conditions = [
            RuleCondition(field="city", operator="equals", value=f"City{i}")
            for i in range(21)
        ]
        with self.assertRaises(ValueError):
            RuleGroup(connector="OR", conditions=conditions)

    # =========================================================================
    # 3. API Endpoints: Fields & Live Preview
    # =========================================================================

    def test_get_supported_fields_metadata(self):
        """GET /segments/fields returns supported fields allowlist and operators."""
        headers = {"Authorization": f"Bearer {self.comm_token}"}
        resp = self.client.get("/segments/fields", headers=headers)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("fields", data)
        self.assertIn("preferred_language", data["fields"])
        self.assertIn("age", data["fields"])
        self.assertIn("consent_status", data["fields"])
        self.assertEqual(data["fields"]["age"]["type"], "numeric")

    def test_preview_rules_endpoint(self):
        """POST /segments/preview returns live matching count and paginated sample records."""
        headers = {"Authorization": f"Bearer {self.comm_token}"}
        payload = {
            "filter_rules": {
                "connector": "AND",
                "conditions": [
                    {"field": "preferred_language", "operator": "equals", "value": "hi"},
                    {"field": "consent_status", "operator": "equals", "value": True},
                ]
            }
        }
        resp = self.client.post("/segments/preview?limit=5&offset=0", json=payload, headers=headers)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["total_matching"], 1)
        self.assertEqual(len(data["sample_members"]), 1)
        self.assertEqual(data["sample_members"][0]["name"], "Aarav Sharma")

    # =========================================================================
    # 4. Segment CRUD & RBAC Enforcement
    # =========================================================================

    def test_create_segment_rbac_and_ownership(self):
        """Test role authorization on POST /segments."""
        payload = {
            "name": "Senior Citizens English",
            "description": "Elderly citizens preferring English communications",
            "filter_rules": {
                "connector": "AND",
                "conditions": [
                    {"field": "age", "operator": "greater_than_or_equal", "value": 60},
                    {"field": "preferred_language", "operator": "equals", "value": "en"},
                ]
            }
        }

        # Communication Team cannot create segments (HTTP 403)
        resp_comm = self.client.post(
            "/segments",
            json=payload,
            headers={"Authorization": f"Bearer {self.comm_token}"}
        )
        self.assertEqual(resp_comm.status_code, 403)

        # Campaign Manager can create segments (HTTP 201)
        resp_mgr = self.client.post(
            "/segments",
            json=payload,
            headers={"Authorization": f"Bearer {self.manager_token}"}
        )
        self.assertEqual(resp_mgr.status_code, 201)
        mgr_data = resp_mgr.json()
        self.assertEqual(mgr_data["name"], "Senior Citizens English")
        self.assertEqual(mgr_data["created_by"], self.manager_user.id)
        self.assertEqual(mgr_data["creator_name"], "Manager Lead A")
        self.assertEqual(mgr_data["matching_audience_count"], 1)  # Robert Dsouza (70, en)

        # Duplicate segment name is rejected (HTTP 409 Conflict)
        resp_dup = self.client.post(
            "/segments",
            json=payload,
            headers={"Authorization": f"Bearer {self.admin_token}"}
        )
        self.assertEqual(resp_dup.status_code, 409)

    def test_list_and_get_segments(self):
        """Test listing and retrieving saved segments."""
        # Create a segment as Admin
        admin_seg_payload = {
            "name": "Tamil WhatsApp Recipients",
            "description": "Tamil speakers on WhatsApp",
            "filter_rules": {
                "connector": "AND",
                "conditions": [
                    {"field": "preferred_language", "operator": "equals", "value": "ta"},
                    {"field": "preferred_channel", "operator": "equals", "value": "whatsapp"},
                ]
            }
        }
        create_resp = self.client.post(
            "/segments",
            json=admin_seg_payload,
            headers={"Authorization": f"Bearer {self.admin_token}"}
        )
        self.assertEqual(create_resp.status_code, 201)
        seg_id = create_resp.json()["id"]

        # All authenticated roles (including Communication Team) can list segments
        list_resp = self.client.get(
            "/segments",
            headers={"Authorization": f"Bearer {self.comm_token}"}
        )
        self.assertEqual(list_resp.status_code, 200)
        items = list_resp.json()["items"]
        self.assertTrue(any(item["id"] == seg_id for item in items))

        # Retrieve single segment
        get_resp = self.client.get(
            f"/segments/{seg_id}",
            headers={"Authorization": f"Bearer {self.comm_token}"}
        )
        self.assertEqual(get_resp.status_code, 200)
        self.assertEqual(get_resp.json()["name"], "Tamil WhatsApp Recipients")
        self.assertEqual(get_resp.json()["matching_audience_count"], 1)

        # Retrieve saved segment preview
        prev_resp = self.client.get(
            f"/segments/{seg_id}/preview",
            headers={"Authorization": f"Bearer {self.comm_token}"}
        )
        self.assertEqual(prev_resp.status_code, 200)
        self.assertEqual(prev_resp.json()["total_matching"], 1)
        self.assertEqual(prev_resp.json()["sample_members"][0]["name"], "Karthik Raman")

    def test_update_and_delete_segment_ownership_rbac(self):
        """Test update and delete permissions: Admin can edit any, Campaign Manager can edit only own."""
        # Create a segment created by Manager Lead A
        mgr_seg_payload = {
            "name": "Manager A Regional Cohort",
            "description": "Initial description",
            "filter_rules": {
                "connector": "AND",
                "conditions": [
                    {"field": "preferred_language", "operator": "equals", "value": "hi"}
                ]
            }
        }
        create_resp = self.client.post(
            "/segments",
            json=mgr_seg_payload,
            headers={"Authorization": f"Bearer {self.manager_token}"}
        )
        self.assertEqual(create_resp.status_code, 201)
        seg_id = create_resp.json()["id"]

        # 1. Communication Team cannot update (HTTP 403)
        update_payload = {"name": "Comm Attempt", "description": "Hacked"}
        resp_comm_put = self.client.put(
            f"/segments/{seg_id}",
            json=update_payload,
            headers={"Authorization": f"Bearer {self.comm_token}"}
        )
        self.assertEqual(resp_comm_put.status_code, 403)

        # 2. Campaign Manager B cannot update Manager A's segment (HTTP 403 Ownership Enforcement)
        resp_other_put = self.client.put(
            f"/segments/{seg_id}",
            json={"name": "Manager B Attempt"},
            headers={"Authorization": f"Bearer {self.other_manager_token}"}
        )
        self.assertEqual(resp_other_put.status_code, 403)
        self.assertIn("own segments", resp_other_put.json()["detail"])

        # 3. Campaign Manager B cannot delete Manager A's segment (HTTP 403)
        resp_other_del = self.client.delete(
            f"/segments/{seg_id}",
            headers={"Authorization": f"Bearer {self.other_manager_token}"}
        )
        self.assertEqual(resp_other_del.status_code, 403)

        # 4. Campaign Manager A can update own segment (HTTP 200)
        resp_owner_put = self.client.put(
            f"/segments/{seg_id}",
            json={"name": "Manager A Regional Cohort Updated", "description": "Updated by owner"},
            headers={"Authorization": f"Bearer {self.manager_token}"}
        )
        self.assertEqual(resp_owner_put.status_code, 200)
        self.assertEqual(resp_owner_put.json()["name"], "Manager A Regional Cohort Updated")

        # 5. Admin can update any segment regardless of creator (HTTP 200)
        resp_admin_put = self.client.put(
            f"/segments/{seg_id}",
            json={"description": "Admin override description"},
            headers={"Authorization": f"Bearer {self.admin_token}"}
        )
        self.assertEqual(resp_admin_put.status_code, 200)
        self.assertEqual(resp_admin_put.json()["description"], "Admin override description")

        # 6. Admin can delete any segment (HTTP 204)
        resp_admin_del = self.client.delete(
            f"/segments/{seg_id}",
            headers={"Authorization": f"Bearer {self.admin_token}"}
        )
        self.assertEqual(resp_admin_del.status_code, 204)

        # 7. Check segment is gone (HTTP 404)
        resp_gone = self.client.get(
            f"/segments/{seg_id}",
            headers={"Authorization": f"Bearer {self.admin_token}"}
        )
        self.assertEqual(resp_gone.status_code, 404)

    def test_unauthenticated_requests_rejected(self):
        """Reject unauthenticated access to all segment endpoints with HTTP 401."""
        self.assertEqual(self.client.get("/segments").status_code, 401)
        self.assertEqual(self.client.post("/segments", json={}).status_code, 401)
        self.assertEqual(self.client.get("/segments/1").status_code, 401)
        self.assertEqual(self.client.put("/segments/1", json={}).status_code, 401)
        self.assertEqual(self.client.delete("/segments/1").status_code, 401)
        self.assertEqual(self.client.post("/segments/preview", json={}).status_code, 401)
        self.assertEqual(self.client.get("/segments/1/preview").status_code, 401)


if __name__ == "__main__":
    unittest.main()

