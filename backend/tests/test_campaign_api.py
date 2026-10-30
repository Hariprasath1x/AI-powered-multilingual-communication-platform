"""Comprehensive HTTP integration test suite for Task 6, Checkpoint 2: Template and Campaign APIs."""

import unittest
from datetime import datetime, timezone, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.main import app
from app.db.base import Base
from app.db.session import get_db
from app.db.seed import seed_default_roles
from app.models.user import User
from app.models.audience import AudienceMember
from app.models.segment import Segment
from app.models.template import Template
from app.models.campaign import Campaign
from app.core.security import get_password_hash, create_access_token


class TestCampaignAPI(unittest.TestCase):
    """Integration test suite covering Template and Campaign HTTP endpoints, RBAC, ownership, and lifecycle."""

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
            hashed_password=get_password_hash("AdminSecret123!"),
            role_id=self.admin_role.id,
            is_active=True,
        )
        self.db.add(self.admin_user)

        # 2. Campaign Manager A (Primary Author)
        self.manager_a = User(
            full_name="Manager Alpha",
            email="manager.a@agency.gov.in",
            hashed_password=get_password_hash("ManagerPass123!"),
            role_id=self.manager_role.id,
            is_active=True,
        )
        self.db.add(self.manager_a)

        # 3. Campaign Manager B (Other Author)
        self.manager_b = User(
            full_name="Manager Beta",
            email="manager.b@agency.gov.in",
            hashed_password=get_password_hash("ManagerPass456!"),
            role_id=self.manager_role.id,
            is_active=True,
        )
        self.db.add(self.manager_b)

        # 4. Communication Team (Read-only role)
        self.comm_user = User(
            full_name="Comm Specialist",
            email="comm.specialist@agency.gov.in",
            hashed_password=get_password_hash("CommPass123!"),
            role_id=self.comm_role.id,
            is_active=True,
        )
        self.db.add(self.comm_user)

        # 5. Audience Members for Segmentation & Previews
        self.aud_delhi_confirmed = AudienceMember(
            name="Aarav Sharma",
            email="aarav.sharma@example.gov.in",
            phone="+919876543210",
            age=32,
            gender="Male",
            city="New Delhi",
            state="Delhi",
            preferred_language="hi",
            preferred_channel="email",
            occupation="Civil Engineer",
            organization_department="Public Works Department",
            consent_status=True,
        )
        self.aud_delhi_unconfirmed = AudienceMember(
            name="Priya Verma",
            email="priya.verma@example.gov.in",
            phone="+919876543211",
            age=25,
            gender="Female",
            city="New Delhi",
            state="Delhi",
            preferred_language="en",
            preferred_channel="sms",
            occupation="Student",
            organization_department="University",
            consent_status=None,
        )
        self.aud_mumbai_confirmed = AudienceMember(
            name="Rohan Joshi",
            email="rohan.joshi@example.gov.in",
            phone="+919876543212",
            age=45,
            gender="Male",
            city="Mumbai",
            state="Maharashtra",
            preferred_language="mr",
            preferred_channel="whatsapp",
            occupation="Doctor",
            organization_department="Health Ministry",
            consent_status=True,
        )
        self.db.add_all([
            self.aud_delhi_confirmed,
            self.aud_delhi_unconfirmed,
            self.aud_mumbai_confirmed,
        ])
        self.db.commit()

        self.db.refresh(self.admin_user)
        self.db.refresh(self.manager_a)
        self.db.refresh(self.manager_b)
        self.db.refresh(self.comm_user)
        self.db.refresh(self.aud_delhi_confirmed)
        self.db.refresh(self.aud_delhi_unconfirmed)
        self.db.refresh(self.aud_mumbai_confirmed)

        # 6. Pre-seeded Segment (Manager A)
        self.seg_delhi = Segment(
            name="National Capital Cohort",
            description="Citizens residing in Delhi",
            filter_rules={
                "logic": "AND",
                "conditions": [
                    {"field": "city", "operator": "equals", "value": "New Delhi"}
                ],
            },
            created_by=self.manager_a.id,
        )
        self.db.add(self.seg_delhi)
        self.db.commit()
        self.db.refresh(self.seg_delhi)

        # Access Tokens
        self.admin_token = create_access_token(self.admin_user.id)
        self.manager_a_token = create_access_token(self.manager_a.id)
        self.manager_b_token = create_access_token(self.manager_b.id)
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

    # =========================================================================
    # 1. Authentication & Route Security Guard Tests
    # =========================================================================

    def test_unauthenticated_requests_rejected(self):
        """Verifies that all template and campaign endpoints strictly reject unauthenticated requests with 401."""
        endpoints = [
            ("GET", "/templates/categories"),
            ("GET", "/templates"),
            ("POST", "/templates"),
            ("GET", "/templates/1"),
            ("PUT", "/templates/1"),
            ("DELETE", "/templates/1"),
            ("GET", "/campaigns/meta"),
            ("GET", "/campaigns"),
            ("POST", "/campaigns"),
            ("GET", "/campaigns/1"),
            ("PUT", "/campaigns/1"),
            ("PATCH", "/campaigns/1/status"),
            ("DELETE", "/campaigns/1"),
            ("GET", "/campaigns/1/preview"),
        ]
        for method, path in endpoints:
            if method == "GET":
                resp = self.client.get(path)
            elif method == "POST":
                resp = self.client.post(path, json={})
            elif method == "PUT":
                resp = self.client.put(path, json={})
            elif method == "PATCH":
                resp = self.client.patch(path, json={})
            elif method == "DELETE":
                resp = self.client.delete(path)
            self.assertEqual(
                resp.status_code,
                401,
                f"Expected 401 for unauthenticated {method} {path}, got {resp.status_code}",
            )

    # =========================================================================
    # 2. Template API Tests
    # =========================================================================

    def test_template_categories_metadata(self):
        """Tests GET /templates/categories returns allowed categories and placeholders to all roles."""
        for token in [self.admin_token, self.manager_a_token, self.comm_token]:
            resp = self.client.get("/templates/categories", headers=self._headers(token))
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertIn("categories", data)
            self.assertIn("allowed_placeholders", data)
            self.assertIn("Healthcare", data["categories"])
            self.assertIn("{name}", data["allowed_placeholders"])

    def test_template_crud_workflow(self):
        """Tests complete template CRUD lifecycle by authorized roles."""
        # 1. Manager A creates template
        create_payload = {
            "title": "Air Quality Emergency Advisory",
            "category": "Disaster Management",
            "body": "Dear {name}, air quality in {city} is severe. Please wear masks outdoors.",
            "language": "en",
            "tags": "smog, pollution, health",
        }
        res_create = self.client.post(
            "/templates",
            headers=self._headers(self.manager_a_token),
            json=create_payload,
        )
        self.assertEqual(res_create.status_code, 201)
        created = res_create.json()
        template_id = created["id"]
        self.assertEqual(created["title"], "Air Quality Emergency Advisory")
        self.assertEqual(created["category"], "Disaster Management")
        self.assertEqual(created["created_by"], self.manager_a.id)
        self.assertIn("{name}", created["placeholders"])
        self.assertIn("{city}", created["placeholders"])

        # 2. Communication Team can read template
        res_get = self.client.get(f"/templates/{template_id}", headers=self._headers(self.comm_token))
        self.assertEqual(res_get.status_code, 200)
        self.assertEqual(res_get.json()["id"], template_id)

        # 3. Manager A updates own template
        res_update = self.client.put(
            f"/templates/{template_id}",
            headers=self._headers(self.manager_a_token),
            json={"title": "Updated Air Advisory", "tags": "smog, updated"},
        )
        self.assertEqual(res_update.status_code, 200)
        self.assertEqual(res_update.json()["title"], "Updated Air Advisory")

        # 4. Admin deletes template
        res_del = self.client.delete(f"/templates/{template_id}", headers=self._headers(self.admin_token))
        self.assertEqual(res_del.status_code, 204)

        # 5. Confirm 404 after deletion
        res_404 = self.client.get(f"/templates/{template_id}", headers=self._headers(self.admin_token))
        self.assertEqual(res_404.status_code, 404)

    def test_template_rbac_and_ownership(self):
        """Verifies that Communication Team cannot mutate and Managers cannot modify others' templates."""
        # Communication Team forbidden from creating templates
        res_comm_create = self.client.post(
            "/templates",
            headers=self._headers(self.comm_token),
            json={
                "title": "Illegal Comm Template",
                "category": "Healthcare",
                "body": "Hello {name}",
            },
        )
        self.assertEqual(res_comm_create.status_code, 403)

        # Manager A creates template
        res_a = self.client.post(
            "/templates",
            headers=self._headers(self.manager_a_token),
            json={
                "title": "Manager A Template",
                "category": "Civic Education",
                "body": "Greetings {name}, election date announced.",
            },
        )
        self.assertEqual(res_a.status_code, 201)
        tmpl_id = res_a.json()["id"]

        # Manager B attempts to update Manager A's template -> 403
        res_b_put = self.client.put(
            f"/templates/{tmpl_id}",
            headers=self._headers(self.manager_b_token),
            json={"title": "Hijacked Title"},
        )
        self.assertEqual(res_b_put.status_code, 403)

        # Manager B attempts to delete Manager A's template -> 403
        res_b_del = self.client.delete(
            f"/templates/{tmpl_id}",
            headers=self._headers(self.manager_b_token),
        )
        self.assertEqual(res_b_del.status_code, 403)

        # Communication Team attempts to update -> 403
        res_comm_put = self.client.put(
            f"/templates/{tmpl_id}",
            headers=self._headers(self.comm_token),
            json={"title": "Comm Edit"},
        )
        self.assertEqual(res_comm_put.status_code, 403)

        # Communication Team attempts to delete -> 403
        res_comm_del = self.client.delete(
            f"/templates/{tmpl_id}",
            headers=self._headers(self.comm_token),
        )
        self.assertEqual(res_comm_del.status_code, 403)

    def test_template_validation_and_duplicate_collision(self):
        """Tests validation errors on invalid placeholders, categories, and title collisions."""
        # 1. Invalid placeholder
        res_invalid_ph = self.client.post(
            "/templates",
            headers=self._headers(self.manager_a_token),
            json={
                "title": "Invalid Placeholder Template",
                "category": "Healthcare",
                "body": "Hello {unsupported_field}",
            },
        )
        self.assertEqual(res_invalid_ph.status_code, 422)

        # 2. Empty braces
        res_empty_braces = self.client.post(
            "/templates",
            headers=self._headers(self.manager_a_token),
            json={
                "title": "Empty Braces Template",
                "category": "Healthcare",
                "body": "Hello {}",
            },
        )
        self.assertEqual(res_empty_braces.status_code, 422)

        # 3. Invalid category
        res_bad_cat = self.client.post(
            "/templates",
            headers=self._headers(self.manager_a_token),
            json={
                "title": "Bad Category Template",
                "category": "UnknownDomain",
                "body": "Hello {name}",
            },
        )
        self.assertEqual(res_bad_cat.status_code, 422)

        # 4. Duplicate title collision -> 409
        self.client.post(
            "/templates",
            headers=self._headers(self.manager_a_token),
            json={
                "title": "Unique Cyclone Warning",
                "category": "Emergency Alert",
                "body": "Alert {name}, cyclone approaching {city}.",
            },
        )
        res_dup = self.client.post(
            "/templates",
            headers=self._headers(self.manager_b_token),
            json={
                "title": "unique cyclone warning",  # Case-insensitive collision
                "category": "Emergency Alert",
                "body": "Another message {name}",
            },
        )
        self.assertEqual(res_dup.status_code, 409)

    def test_template_search_and_pagination(self):
        """Tests filtering templates by category, language, search term, and pagination."""
        for i in range(5):
            self.client.post(
                "/templates",
                headers=self._headers(self.admin_token),
                json={
                    "title": f"Health Tip #{i}",
                    "category": "Healthcare",
                    "body": f"Daily health tip #{i} for {{name}}.",
                    "language": "en" if i % 2 == 0 else "hi",
                    "tags": "wellness, tips",
                },
            )

        # Search term filter (using params dict so '#' is properly URL-encoded)
        res_search = self.client.get(
            "/templates",
            headers=self._headers(self.comm_token),
            params={"search": "Tip #3"},
        )
        self.assertEqual(res_search.status_code, 200)
        self.assertEqual(res_search.json()["total"], 1)

        # Language filter
        res_lang = self.client.get(
            "/templates",
            headers=self._headers(self.comm_token),
            params={"language": "hi"},
        )
        self.assertEqual(res_lang.status_code, 200)
        self.assertEqual(res_lang.json()["total"], 2)

        # Pagination limit
        res_page = self.client.get(
            "/templates",
            headers=self._headers(self.comm_token),
            params={"page": 1, "page_size": 2},
        )
        self.assertEqual(res_page.status_code, 200)
        self.assertEqual(len(res_page.json()["items"]), 2)

    # =========================================================================
    # 3. Campaign API Tests
    # =========================================================================

    def test_campaign_metadata_endpoint(self):
        """Tests GET /campaigns/meta returns types, priorities, statuses, channels."""
        for token in [self.admin_token, self.manager_a_token, self.comm_token]:
            resp = self.client.get("/campaigns/meta", headers=self._headers(token))
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertIn("types", data)
            self.assertIn("priorities", data)
            self.assertIn("statuses", data)
            self.assertIn("channels", data)
            self.assertIn("Awareness", data["types"])
            self.assertIn("Draft", data["statuses"])
            self.assertIn("Email", data["channels"])

    def test_campaign_crud_workflow(self):
        """Tests campaign creation, retrieval with reach calculation, update, and deletion."""
        # Create helper template
        tmpl_res = self.client.post(
            "/templates",
            headers=self._headers(self.manager_a_token),
            json={
                "title": "Clean Water Protocol",
                "category": "Healthcare",
                "body": "Dear {name}, clean drinking water centers opened in {city}.",
            },
        )
        tmpl_id = tmpl_res.json()["id"]

        # 1. Manager A creates campaign
        start_time = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
        end_time = (datetime.now(timezone.utc) + timedelta(days=5)).isoformat()
        create_payload = {
            "name": "Delhi Safe Water Campaign",
            "campaign_type": "Awareness",
            "objective": "Distribute clean water guidelines across Delhi.",
            "priority": "High",
            "channels": ["Email", "SMS"],
            "template_id": tmpl_id,
            "segment_ids": [self.seg_delhi.id],
            "start_date": start_time,
            "end_date": end_time,
        }
        res_create = self.client.post(
            "/campaigns",
            headers=self._headers(self.manager_a_token),
            json=create_payload,
        )
        self.assertEqual(res_create.status_code, 201)
        camp = res_create.json()
        camp_id = camp["id"]
        self.assertEqual(camp["name"], "Delhi Safe Water Campaign")
        self.assertEqual(camp["status"], "Draft")
        self.assertEqual(camp["created_by"], self.manager_a.id)
        self.assertEqual(len(camp["segments"]), 1)
        self.assertEqual(camp["template_id"], tmpl_id)
        # Verify deduplicated reach & tri-state consent:
        # Segment matches 2 citizens in Delhi: Aarav (consent=True) and Priya (consent=None)
        # Total target audience: 2, Confirmed consent: 1
        self.assertEqual(camp["total_target_audience"], 2)
        self.assertEqual(camp["confirmed_consent_audience"], 1)

        # 2. Read campaign details
        res_get = self.client.get(f"/campaigns/{camp_id}", headers=self._headers(self.comm_token))
        self.assertEqual(res_get.status_code, 200)
        self.assertEqual(res_get.json()["id"], camp_id)

        # 3. Update campaign configuration
        res_update = self.client.put(
            f"/campaigns/{camp_id}",
            headers=self._headers(self.manager_a_token),
            json={"priority": "Medium", "objective": "Revised mission"},
        )
        self.assertEqual(res_update.status_code, 200)
        self.assertEqual(res_update.json()["priority"], "Medium")

        # 4. Delete campaign in Draft
        res_del = self.client.delete(f"/campaigns/{camp_id}", headers=self._headers(self.manager_a_token))
        self.assertEqual(res_del.status_code, 204)

        # Confirm 404
        res_404 = self.client.get(f"/campaigns/{camp_id}", headers=self._headers(self.manager_a_token))
        self.assertEqual(res_404.status_code, 404)

    def test_campaign_rbac_and_ownership(self):
        """Verifies that Communication Team cannot mutate campaigns and Managers cannot mutate others' campaigns."""
        # Communication Team forbidden from creating campaigns
        res_comm_create = self.client.post(
            "/campaigns",
            headers=self._headers(self.comm_token),
            json={
                "name": "Comm Illegal Campaign",
                "campaign_type": "Awareness",
                "channels": ["Email"],
            },
        )
        self.assertEqual(res_comm_create.status_code, 403)

        # Manager A creates campaign
        res_a = self.client.post(
            "/campaigns",
            headers=self._headers(self.manager_a_token),
            json={
                "name": "Manager A Campaign",
                "campaign_type": "Educational",
                "channels": ["SMS"],
            },
        )
        self.assertEqual(res_a.status_code, 201)
        camp_id = res_a.json()["id"]

        # Manager B forbidden from updating Manager A's campaign
        res_b_put = self.client.put(
            f"/campaigns/{camp_id}",
            headers=self._headers(self.manager_b_token),
            json={"name": "Hijacked Name"},
        )
        self.assertEqual(res_b_put.status_code, 403)

        # Manager B forbidden from status transitioning Manager A's campaign
        res_b_status = self.client.patch(
            f"/campaigns/{camp_id}/status",
            headers=self._headers(self.manager_b_token),
            json={"status": "In Review"},
        )
        self.assertEqual(res_b_status.status_code, 403)

        # Manager B forbidden from deleting Manager A's campaign
        res_b_del = self.client.delete(
            f"/campaigns/{camp_id}",
            headers=self._headers(self.manager_b_token),
        )
        self.assertEqual(res_b_del.status_code, 403)

        # Communication Team forbidden from updating, transitioning, or deleting
        res_comm_put = self.client.put(
            f"/campaigns/{camp_id}",
            headers=self._headers(self.comm_token),
            json={"name": "Comm Name"},
        )
        self.assertEqual(res_comm_put.status_code, 403)

        res_comm_patch = self.client.patch(
            f"/campaigns/{camp_id}/status",
            headers=self._headers(self.comm_token),
            json={"status": "In Review"},
        )
        self.assertEqual(res_comm_patch.status_code, 403)

        res_comm_del = self.client.delete(
            f"/campaigns/{camp_id}",
            headers=self._headers(self.comm_token),
        )
        self.assertEqual(res_comm_del.status_code, 403)

        # Admin CAN update and delete Manager A's campaign
        res_admin_put = self.client.put(
            f"/campaigns/{camp_id}",
            headers=self._headers(self.admin_token),
            json={"objective": "Admin updated objective"},
        )
        self.assertEqual(res_admin_put.status_code, 200)

        res_admin_del = self.client.delete(
            f"/campaigns/{camp_id}",
            headers=self._headers(self.admin_token),
        )
        self.assertEqual(res_admin_del.status_code, 204)

    def test_campaign_validation_and_integrity(self):
        """Tests validation errors on missing references, invalid dates, and duplicate names."""
        # 1. Non-existent segment ID -> 404
        res_seg_404 = self.client.post(
            "/campaigns",
            headers=self._headers(self.manager_a_token),
            json={
                "name": "Invalid Segment Campaign",
                "campaign_type": "Awareness",
                "channels": ["Email"],
                "segment_ids": [9999],
            },
        )
        self.assertEqual(res_seg_404.status_code, 404)

        # 2. Non-existent template ID -> 404
        res_tmpl_404 = self.client.post(
            "/campaigns",
            headers=self._headers(self.manager_a_token),
            json={
                "name": "Invalid Template Campaign",
                "campaign_type": "Awareness",
                "channels": ["Email"],
                "template_id": 9999,
            },
        )
        self.assertEqual(res_tmpl_404.status_code, 404)

        # 3. Invalid dates: end_date < start_date -> 422
        now = datetime.now(timezone.utc)
        res_date_422 = self.client.post(
            "/campaigns",
            headers=self._headers(self.manager_a_token),
            json={
                "name": "Invalid Dates Campaign",
                "campaign_type": "Awareness",
                "channels": ["Email"],
                "start_date": (now + timedelta(days=5)).isoformat(),
                "end_date": (now + timedelta(days=2)).isoformat(),
            },
        )
        self.assertEqual(res_date_422.status_code, 422)

        # 4. Duplicate campaign name -> 409 Conflict
        self.client.post(
            "/campaigns",
            headers=self._headers(self.manager_a_token),
            json={
                "name": "Immunization Drive 2026",
                "campaign_type": "Awareness",
                "channels": ["SMS"],
            },
        )
        res_dup = self.client.post(
            "/campaigns",
            headers=self._headers(self.manager_b_token),
            json={
                "name": "immunization drive 2026",
                "campaign_type": "Awareness",
                "channels": ["SMS"],
            },
        )
        self.assertEqual(res_dup.status_code, 409)

    def test_campaign_lifecycle_transitions_and_guards(self):
        """Verifies state machine transitions, guards (requires segments and template), and edit locks."""
        # Create template
        tmpl_res = self.client.post(
            "/templates",
            headers=self._headers(self.manager_a_token),
            json={
                "title": "Flood Alert Protocol",
                "category": "Emergency Alert",
                "body": "Emergency alert for {name}: move to higher ground.",
            },
        )
        tmpl_id = tmpl_res.json()["id"]

        # Create campaign without segments or template
        camp_res = self.client.post(
            "/campaigns",
            headers=self._headers(self.manager_a_token),
            json={
                "name": "River Basin Evacuation",
                "campaign_type": "Emergency Alert",
                "channels": ["Voice", "SMS"],
            },
        )
        camp_id = camp_res.json()["id"]

        # Guard 1: Transition to 'In Review' fails without segment and template -> 400
        res_guard_fail = self.client.patch(
            f"/campaigns/{camp_id}/status",
            headers=self._headers(self.manager_a_token),
            json={"status": "In Review"},
        )
        self.assertEqual(res_guard_fail.status_code, 400)
        self.assertIn("segment must be attached", res_guard_fail.json()["detail"])

        # Attach segment, still missing template -> 400
        self.client.put(
            f"/campaigns/{camp_id}",
            headers=self._headers(self.manager_a_token),
            json={"segment_ids": [self.seg_delhi.id]},
        )
        res_guard_fail2 = self.client.patch(
            f"/campaigns/{camp_id}/status",
            headers=self._headers(self.manager_a_token),
            json={"status": "In Review"},
        )
        self.assertEqual(res_guard_fail2.status_code, 400)
        self.assertIn("template must be linked", res_guard_fail2.json()["detail"])

        # Attach template
        self.client.put(
            f"/campaigns/{camp_id}",
            headers=self._headers(self.manager_a_token),
            json={"template_id": tmpl_id},
        )

        # Valid transition: Draft -> In Review
        res_in_review = self.client.patch(
            f"/campaigns/{camp_id}/status",
            headers=self._headers(self.manager_a_token),
            json={"status": "In Review"},
        )
        self.assertEqual(res_in_review.status_code, 200)
        self.assertEqual(res_in_review.json()["status"], "In Review")

        # Valid transition: In Review -> Approved
        res_approved = self.client.patch(
            f"/campaigns/{camp_id}/status",
            headers=self._headers(self.manager_a_token),
            json={"status": "Approved"},
        )
        self.assertEqual(res_approved.status_code, 200)
        self.assertEqual(res_approved.json()["status"], "Approved")

        # Edit Lock: Cannot modify core campaign fields when Approved -> 400
        res_locked_put = self.client.put(
            f"/campaigns/{camp_id}",
            headers=self._headers(self.manager_a_token),
            json={"objective": "Trying to edit while approved"},
        )
        self.assertEqual(res_locked_put.status_code, 400)

        # Deletion Guard: Cannot delete while Approved -> 400
        res_locked_del = self.client.delete(
            f"/campaigns/{camp_id}",
            headers=self._headers(self.manager_a_token),
        )
        self.assertEqual(res_locked_del.status_code, 400)

        # Scheduling Guard: Transition Approved -> Scheduled fails if start_date is not set
        res_sched_fail = self.client.patch(
            f"/campaigns/{camp_id}/status",
            headers=self._headers(self.manager_a_token),
            json={"status": "Scheduled"},
        )
        self.assertEqual(res_sched_fail.status_code, 400)
        self.assertIn("start_date", res_sched_fail.json()["detail"])

        # Move back to Draft to set start_date
        self.client.patch(
            f"/campaigns/{camp_id}/status",
            headers=self._headers(self.manager_a_token),
            json={"status": "Draft"},
        )
        start_time = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
        self.client.put(
            f"/campaigns/{camp_id}",
            headers=self._headers(self.manager_a_token),
            json={"start_date": start_time},
        )
        # Transition Draft -> Approved -> Scheduled
        self.client.patch(
            f"/campaigns/{camp_id}/status",
            headers=self._headers(self.manager_a_token),
            json={"status": "Approved"},
        )
        res_sched_ok = self.client.patch(
            f"/campaigns/{camp_id}/status",
            headers=self._headers(self.manager_a_token),
            json={"status": "Scheduled"},
        )
        self.assertEqual(res_sched_ok.status_code, 200)
        self.assertEqual(res_sched_ok.json()["status"], "Scheduled")

        # Move Scheduled -> Draft -> Archived
        self.client.patch(
            f"/campaigns/{camp_id}/status",
            headers=self._headers(self.manager_a_token),
            json={"status": "Draft"},
        )
        res_archived = self.client.patch(
            f"/campaigns/{camp_id}/status",
            headers=self._headers(self.manager_a_token),
            json={"status": "Archived"},
        )
        self.assertEqual(res_archived.status_code, 200)
        self.assertEqual(res_archived.json()["status"], "Archived")

        # Terminal state: Cannot transition out of Archived -> 400
        res_terminal = self.client.patch(
            f"/campaigns/{camp_id}/status",
            headers=self._headers(self.manager_a_token),
            json={"status": "Draft"},
        )
        self.assertEqual(res_terminal.status_code, 400)

        # Deletion is allowed on Archived campaigns -> 204
        res_del_archived = self.client.delete(
            f"/campaigns/{camp_id}",
            headers=self._headers(self.manager_a_token),
        )
        self.assertEqual(res_del_archived.status_code, 204)

    def test_campaign_search_and_pagination(self):
        """Tests filtering campaigns by status, type, priority, search term, and pagination."""
        priorities = ["Low", "Medium", "High"]
        types = ["Awareness", "Educational", "Emergency Alert"]
        for i in range(6):
            self.client.post(
                "/campaigns",
                headers=self._headers(self.manager_a_token),
                json={
                    "name": f"Civic Campaign #{i}",
                    "campaign_type": types[i % len(types)],
                    "objective": f"Civic engagement initiative #{i}",
                    "priority": priorities[i % len(priorities)],
                    "channels": ["Email"],
                },
            )

        # 1. Search term filter
        res_search = self.client.get(
            "/campaigns",
            headers=self._headers(self.comm_token),
            params={"search": "Campaign #2"},
        )
        self.assertEqual(res_search.status_code, 200)
        self.assertEqual(res_search.json()["total"], 1)

        # 2. Priority filter
        res_priority = self.client.get(
            "/campaigns",
            headers=self._headers(self.comm_token),
            params={"priority": "High"},
        )
        self.assertEqual(res_priority.status_code, 200)
        self.assertEqual(res_priority.json()["total"], 2)

        # 3. Status filter (all created are in Draft)
        res_status = self.client.get(
            "/campaigns",
            headers=self._headers(self.comm_token),
            params={"status": "Draft"},
        )
        self.assertEqual(res_status.status_code, 200)
        self.assertEqual(res_status.json()["total"], 6)

        # 4. Pagination
        res_paged = self.client.get(
            "/campaigns",
            headers=self._headers(self.comm_token),
            params={"page": 1, "page_size": 3},
        )
        self.assertEqual(res_paged.status_code, 200)
        self.assertEqual(len(res_paged.json()["items"]), 3)
        self.assertEqual(res_paged.json()["total_pages"], 2)

    def test_campaign_preview_endpoint(self):
        """Tests safe preview rendering across multiple communication channels via GET and POST."""
        # 1. Create template with multiple placeholders
        tmpl_res = self.client.post(
            "/templates",
            headers=self._headers(self.manager_a_token),
            json={
                "title": "Hospital Inauguration",
                "category": "Healthcare",
                "body": "Hello {name}, visit the new health center in {city}, {state}. Department: {organization_department}.",
            },
        )
        tmpl_id = tmpl_res.json()["id"]

        # 2. Create campaign attached to template and Delhi segment
        camp_res = self.client.post(
            "/campaigns",
            headers=self._headers(self.manager_a_token),
            json={
                "name": "Health Center Launch",
                "campaign_type": "Awareness",
                "channels": ["Email", "SMS", "WhatsApp", "Voice"],
                "template_id": tmpl_id,
                "segment_ids": [self.seg_delhi.id],
            },
        )
        camp_id = camp_res.json()["id"]

        # 3. GET /campaigns/{id}/preview with default matching recipient
        res_preview = self.client.get(
            f"/campaigns/{camp_id}/preview",
            headers=self._headers(self.comm_token),
        )
        self.assertEqual(res_preview.status_code, 200)
        data = res_preview.json()
        self.assertEqual(data["campaign_id"], camp_id)
        self.assertIn("sample_recipient", data)
        self.assertIn("channel_previews", data)

        # Channel-specific metric assertions
        channels = data["channel_previews"]
        self.assertIn("Email", channels)
        self.assertIn("SMS", channels)
        self.assertIn("WhatsApp", channels)
        self.assertIn("Voice", channels)

        # Email metrics
        self.assertIn("word_count", channels["Email"]["metrics"])
        self.assertIn("[MEDIUM]", channels["Email"]["title_or_subject"])

        # SMS metrics
        self.assertIn("character_count", channels["SMS"]["metrics"])
        self.assertIn("segment_count", channels["SMS"]["metrics"])
        self.assertGreater(channels["SMS"]["metrics"]["character_count"], 10)

        # Voice metrics
        self.assertIn("estimated_duration_seconds", channels["Voice"]["metrics"])
        self.assertIn("130 words per minute", channels["Voice"]["metrics"]["pacing"])

        # 4. POST /campaigns/{id}/preview with custom placeholders override
        res_custom_preview = self.client.post(
            f"/campaigns/{camp_id}/preview",
            headers=self._headers(self.comm_token),
            json={
                "custom_placeholders": {
                    "{name}": "Chief Minister",
                    "{city}": "Connaught Place",
                    "{state}": "National Territory",
                    "{organization_department}": "Secretariat",
                }
            },
        )
        self.assertEqual(res_custom_preview.status_code, 200)
        custom_data = res_custom_preview.json()
        self.assertIn("Chief Minister", custom_data["rendered_content"])
        self.assertIn("Connaught Place", custom_data["rendered_content"])

        # 5. Preview on campaign without template -> 400
        camp_notmpl = self.client.post(
            "/campaigns",
            headers=self._headers(self.manager_a_token),
            json={
                "name": "No Template Campaign",
                "campaign_type": "Awareness",
                "channels": ["SMS"],
            },
        ).json()["id"]

        res_no_tmpl = self.client.get(
            f"/campaigns/{camp_notmpl}/preview",
            headers=self._headers(self.comm_token),
        )
        self.assertEqual(res_no_tmpl.status_code, 400)
        self.assertIn("no content template", res_no_tmpl.json()["detail"])


if __name__ == "__main__":
    unittest.main()
