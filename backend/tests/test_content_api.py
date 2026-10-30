"""Comprehensive HTTP integration test suite for Task 7, Checkpoint 2: AI Content Studio APIs."""

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
from app.models.campaign import Campaign
from app.models.template import Template
from app.core.security import get_password_hash, create_access_token


class TestContentAPI(unittest.TestCase):
    """Integration test suite covering Content Studio endpoints, RBAC, ownership, translation, and lifecycle."""

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

        # Users
        self.admin_user = User(
            full_name="Admin Director",
            email="admin.director@agency.gov.in",
            hashed_password=get_password_hash("AdminSecret123!"),
            role_id=self.admin_role.id,
            is_active=True,
        )
        self.manager_a = User(
            full_name="Manager Alpha",
            email="manager.a@agency.gov.in",
            hashed_password=get_password_hash("ManagerPass123!"),
            role_id=self.manager_role.id,
            is_active=True,
        )
        self.manager_b = User(
            full_name="Manager Beta",
            email="manager.b@agency.gov.in",
            hashed_password=get_password_hash("ManagerPass456!"),
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
        self.db.add_all([self.admin_user, self.manager_a, self.manager_b, self.comm_user])
        self.db.commit()

        # Seed sample campaign for Manager A
        self.campaign = Campaign(
            name="Coastal Tsunami Preparedness",
            campaign_type="Emergency Alert",
            objective="Emergency awareness for fishing communities",
            priority="High",
            status="Draft",
            channels=["SMS", "WhatsApp"],
            created_by=self.manager_a.id,
        )
        self.db.add(self.campaign)
        self.db.commit()

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

    # -------------------------------------------------------------
    # 1. Unauthenticated & Metadata Tests
    # -------------------------------------------------------------

    def test_unauthenticated_requests_rejected(self):
        """Unauthenticated requests to protected endpoints return 401."""
        res_list = self.client.get("/content")
        self.assertEqual(res_list.status_code, 401)

        res_gen = self.client.post("/content/generate", json={"topic": "Dengue", "objective": "Awareness", "category": "Healthcare"})
        self.assertEqual(res_gen.status_code, 401)

        res_trans = self.client.post("/content/1/translate", json={"target_language": "ta"})
        self.assertEqual(res_trans.status_code, 401)

    def test_metadata_endpoints(self):
        """Metadata endpoints return allowlisted languages, tones, and channels."""
        # Supported languages
        res_lang = self.client.get("/content/languages", headers=self._headers(self.comm_token))
        self.assertEqual(res_lang.status_code, 200)
        codes = [item["code"] for item in res_lang.json()["languages"]]
        self.assertIn("en", codes)
        self.assertIn("ta", codes)
        self.assertIn("hi", codes)

        # Supported tones
        res_tones = self.client.get("/content/tones", headers=self._headers(self.comm_token))
        self.assertEqual(res_tones.status_code, 200)
        tones = res_tones.json()["tones"]
        self.assertIn("urgent", tones)
        self.assertIn("empathetic", tones)

        # Supported channels
        res_chans = self.client.get("/content/channels", headers=self._headers(self.comm_token))
        self.assertEqual(res_chans.status_code, 200)
        chans = res_chans.json()["channels"]
        self.assertIn("Email", chans)
        self.assertIn("SMS", chans)
        self.assertIn("WhatsApp", chans)
        self.assertIn("Voice", chans)

    # -------------------------------------------------------------
    # 2. RBAC & Authoring Permission Tests
    # -------------------------------------------------------------

    def test_rbac_authoring_permissions(self):
        """Communication Team cannot author or review; Managers and Admins can."""
        gen_payload = {
            "topic": "Clean Drinking Water",
            "objective": "Advise boiling water during monsoon",
            "category": "Healthcare",
            "tone": "informative",
            "channel": "SMS",
            "source_language": "en",
        }

        # Comm Team user gets 403 Forbidden
        res_comm = self.client.post("/content/generate", json=gen_payload, headers=self._headers(self.comm_token))
        self.assertEqual(res_comm.status_code, 403)

        # Manager gets 201 Created
        res_mgr = self.client.post("/content/generate", json=gen_payload, headers=self._headers(self.manager_a_token))
        self.assertEqual(res_mgr.status_code, 201)
        asset_id = res_mgr.json()["id"]

        # Comm Team cannot review
        res_rev = self.client.patch(
            f"/content/{asset_id}/review",
            json={"review_status": "In Review"},
            headers=self._headers(self.comm_token),
        )
        self.assertEqual(res_rev.status_code, 403)

    # -------------------------------------------------------------
    # 3. Content Generation & Channel Metrics
    # -------------------------------------------------------------

    def test_generate_content_api_success(self):
        """Generate content returns channel simulation metrics and Draft review status."""
        payload = {
            "topic": "Heatstroke Prevention",
            "objective": "Urgent directives for outdoor workers",
            "audience_description": "Outdoor laborers and senior citizens",
            "category": "Healthcare",
            "tone": "urgent",
            "channel": "SMS",
            "source_language": "en",
            "facts": "Stay hydrated. Rest between 12pm-3pm. Free ORS at clinics.",
        }

        res = self.client.post("/content/generate", json=payload, headers=self._headers(self.manager_a_token))
        self.assertEqual(res.status_code, 201)
        data = res.json()

        self.assertEqual(data["channel"], "SMS")
        self.assertEqual(data["tone"], "urgent")
        self.assertEqual(data["review_status"], "Draft")  # Human review required
        self.assertEqual(data["operation_type"], "generation")
        self.assertGreater(data["character_count"], 10)
        self.assertGreaterEqual(data["sms_segment_count"], 1)
        self.assertIn("{name}", data["detected_placeholders"])
        self.assertIn("{city}", data["detected_placeholders"])

    def test_manual_content_authoring(self):
        """Manually author a draft content asset in the studio."""
        payload = {
            "title": "Manual Civic Notice",
            "body": "Dear {name}, please attend the municipal town hall in {city}.",
            "category": "Civic Services",
            "tone": "formal",
            "channel": "Email",
            "source_language": "en",
        }
        res = self.client.post("/content/manual", json=payload, headers=self._headers(self.manager_a_token))
        self.assertEqual(res.status_code, 201)
        data = res.json()
        self.assertEqual(data["title"], "Manual Civic Notice")
        self.assertEqual(data["operation_type"], "human_edit")

    # -------------------------------------------------------------
    # 4. Multilingual Translation & Lineage
    # -------------------------------------------------------------

    def test_translate_content_api_and_lineage_retrieval(self):
        """Translating creates child variant and variant endpoint retrieves lineage."""
        # Step 1: Generate initial asset
        gen_res = self.client.post(
            "/content/generate",
            json={
                "topic": "Flash Flood Advisory",
                "objective": "Move to higher ground",
                "category": "Disaster Preparedness",
                "tone": "urgent",
                "channel": "WhatsApp",
                "source_language": "en",
                "facts": "Helpline 1070. Community Hall shelter.",
            },
            headers=self._headers(self.manager_a_token),
        )
        self.assertEqual(gen_res.status_code, 201)
        root_id = gen_res.json()["id"]

        # Step 2: Translate into Tamil ('ta')
        trans_res = self.client.post(
            f"/content/{root_id}/translate",
            json={"target_language": "ta", "notes": "Emergency coastal warning"},
            headers=self._headers(self.manager_a_token),
        )
        self.assertEqual(trans_res.status_code, 201)
        var_data = trans_res.json()

        self.assertEqual(var_data["target_language"], "ta")
        self.assertEqual(var_data["parent_id"], root_id)
        self.assertEqual(var_data["operation_type"], "translation")
        self.assertEqual(var_data["review_status"], "Draft")

        # Verify placeholders preserved in translated copy
        self.assertIn("{name}", var_data["detected_placeholders"])
        self.assertIn("{city}", var_data["detected_placeholders"])

        # Step 3: Get variants lineage
        var_list_res = self.client.get(f"/content/{root_id}/variants", headers=self._headers(self.manager_a_token))
        self.assertEqual(var_list_res.status_code, 200)
        variants = var_list_res.json()
        self.assertEqual(len(variants), 2)
        self.assertEqual(variants[0]["id"], root_id)
        self.assertEqual(variants[1]["id"], var_data["id"])

    def test_translate_disallows_same_language(self):
        """Translating to identical active language returns 400."""
        gen_res = self.client.post(
            "/content/generate",
            json={
                "topic": "Vaccination Camp",
                "objective": "Announce polio drive",
                "category": "Healthcare",
                "channel": "SMS",
                "source_language": "en",
            },
            headers=self._headers(self.manager_a_token),
        )
        asset_id = gen_res.json()["id"]

        res = self.client.post(
            f"/content/{asset_id}/translate",
            json={"target_language": "en"},
            headers=self._headers(self.manager_a_token),
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("identical", res.json()["detail"])

    # -------------------------------------------------------------
    # 5. Ownership Enforcement
    # -------------------------------------------------------------

    def test_ownership_enforcement(self):
        """Manager B cannot edit or delete Manager A's content; Admin can."""
        gen_res = self.client.post(
            "/content/generate",
            json={
                "topic": "Manager A Notice",
                "objective": "Test ownership guards",
                "category": "Civic Services",
                "channel": "Email",
            },
            headers=self._headers(self.manager_a_token),
        )
        asset_id = gen_res.json()["id"]

        # Manager B update attempt -> 403 Forbidden
        update_res_b = self.client.put(
            f"/content/{asset_id}",
            json={"title": "Manager B Hijack"},
            headers=self._headers(self.manager_b_token),
        )
        self.assertEqual(update_res_b.status_code, 403)

        # Manager B delete attempt -> 403 Forbidden
        delete_res_b = self.client.delete(
            f"/content/{asset_id}",
            headers=self._headers(self.manager_b_token),
        )
        self.assertEqual(delete_res_b.status_code, 403)

        # Admin CAN update
        update_res_admin = self.client.put(
            f"/content/{asset_id}",
            json={"title": "Admin Verified Title"},
            headers=self._headers(self.admin_token),
        )
        self.assertEqual(update_res_admin.status_code, 200)
        self.assertEqual(update_res_admin.json()["title"], "Admin Verified Title")

    # -------------------------------------------------------------
    # 6. Review Lifecycle & Re-edit Protection
    # -------------------------------------------------------------

    def test_review_lifecycle_and_reedit_protection(self):
        """Full review cycle: Draft -> In Review -> Approved; human edit resets to In Review."""
        gen_res = self.client.post(
            "/content/generate",
            json={
                "topic": "Clean Air Initiative",
                "objective": "Promote public transit",
                "category": "Environment",
                "channel": "Email",
            },
            headers=self._headers(self.manager_a_token),
        )
        asset_id = gen_res.json()["id"]

        # Move to In Review
        res_review = self.client.patch(
            f"/content/{asset_id}/review",
            json={"review_status": "In Review", "review_notes": "Needs scientific factcheck"},
            headers=self._headers(self.manager_a_token),
        )
        self.assertEqual(res_review.status_code, 200)
        self.assertEqual(res_review.json()["review_status"], "In Review")
        self.assertEqual(res_review.json()["reviewed_by"], self.manager_a.id)

        # Move to Approved
        res_approve = self.client.patch(
            f"/content/{asset_id}/review",
            json={"review_status": "Approved", "review_notes": "Factcheck passed"},
            headers=self._headers(self.admin_token),
        )
        self.assertEqual(res_approve.status_code, 200)
        self.assertEqual(res_approve.json()["review_status"], "Approved")

        # Edit approved content -> Automatically resets review_status back to In Review
        res_edit = self.client.put(
            f"/content/{asset_id}",
            json={"body": "Modified content after approval requires re-review."},
            headers=self._headers(self.manager_a_token),
        )
        self.assertEqual(res_edit.status_code, 200)
        self.assertEqual(res_edit.json()["review_status"], "In Review")
        self.assertEqual(res_edit.json()["operation_type"], "human_edit")

    # -------------------------------------------------------------
    # 7. Attach to Campaign & Template
    # -------------------------------------------------------------

    def test_attach_content_to_campaign_and_template(self):
        """Attach updates campaign draft body and creates template without bypassing campaign approval."""
        gen_res = self.client.post(
            "/content/generate",
            json={
                "topic": "Tsunami Warning Protocol",
                "objective": "Evacuation instructions",
                "category": "Disaster Preparedness",
                "channel": "SMS",
            },
            headers=self._headers(self.manager_a_token),
        )
        asset_id = gen_res.json()["id"]

        attach_payload = {
            "campaign_id": self.campaign.id,
            "save_as_template": True,
            "template_name": "Tsunami Protocol SMS Template",
            "template_category": "Disaster Preparedness",
        }

        res = self.client.post(
            f"/content/{asset_id}/attach",
            json=attach_payload,
            headers=self._headers(self.manager_a_token),
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["attached_campaign_id"], self.campaign.id)
        self.assertIn("saved_template_id", data)

        # Verify campaign state in DB: template linked, but status strictly unchanged (Draft)
        camp_res = self.client.get(f"/campaigns/{self.campaign.id}", headers=self._headers(self.manager_a_token))
        self.assertEqual(camp_res.status_code, 200)
        camp_data = camp_res.json()
        self.assertEqual(camp_data["status"], "Draft")  # Safety check: no bypass to Approved/Scheduled
        self.assertEqual(camp_data["template_id"], data["saved_template_id"])
        self.assertTrue(len(camp_data["template_body"]) > 10)

    # -------------------------------------------------------------
    # 8. Delete & Pagination Filters
    # -------------------------------------------------------------

    def test_delete_content_asset(self):
        """Deleting draft content asset removes it and subsequent GET returns 404."""
        gen_res = self.client.post(
            "/content/generate",
            json={
                "topic": "Temp Draft",
                "objective": "Delete test",
                "category": "Civic Services",
                "channel": "Voice",
            },
            headers=self._headers(self.manager_a_token),
        )
        asset_id = gen_res.json()["id"]

        del_res = self.client.delete(f"/content/{asset_id}", headers=self._headers(self.manager_a_token))
        self.assertEqual(del_res.status_code, 200)

        get_res = self.client.get(f"/content/{asset_id}", headers=self._headers(self.manager_a_token))
        self.assertEqual(get_res.status_code, 404)

    def test_list_content_assets_with_filters(self):
        """List content assets with channel and category filters."""
        # Create 2 distinct assets
        self.client.post(
            "/content/generate",
            json={"topic": "Dengue Alert", "objective": "Dengue", "category": "Healthcare", "channel": "SMS"},
            headers=self._headers(self.manager_a_token),
        )
        self.client.post(
            "/content/generate",
            json={"topic": "Tree Planting Drive", "objective": "Ecology", "category": "Environment", "channel": "Email"},
            headers=self._headers(self.manager_a_token),
        )

        # Filter by channel=SMS
        res_sms = self.client.get("/content?channel=SMS", headers=self._headers(self.manager_a_token))
        self.assertEqual(res_sms.status_code, 200)
        items_sms = res_sms.json()["items"]
        for it in items_sms:
            self.assertEqual(it["channel"], "SMS")

        # Filter by category=Environment
        res_env = self.client.get("/content?category=Environment", headers=self._headers(self.manager_a_token))
        self.assertEqual(res_env.status_code, 200)
        items_env = res_env.json()["items"]
        for it in items_env:
            self.assertEqual(it["category"], "Environment")


if __name__ == "__main__":
    unittest.main()
