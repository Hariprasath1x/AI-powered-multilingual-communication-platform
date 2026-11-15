"""Test suite for Audience-Specific Content Personalization (Milestone 2, Task 9.A)."""

import unittest
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.main import app
from app.db.base import Base
from app.db.session import get_db
from app.db.seed import seed_default_roles
from app.models.content_asset import ContentAsset
from app.models.content_variant import ContentVariant
from app.models.segment import Segment
from app.models.audience import AudienceMember
from app.models.campaign import Campaign
from app.models.user import User
from app.models.compliance_rule import ComplianceRule
from app.core.security import get_password_hash, create_access_token
from app.schemas.content_variant import (
    ContentPersonalizeRequest,
    ContentVariantUpdate,
    RecipientPreviewRequest,
)
from app.services.personalization_service import (
    compile_segment_persona,
    compute_variant_hash,
    personalize_content_asset,
    list_content_variants,
    update_content_variant,
    delete_content_variant,
    preview_recipient_message,
)


class TestPersonalizationUnit(unittest.TestCase):
    """Unit tests for segment persona compilation and deterministic variant generation."""

    def test_compile_segment_persona_demographics(self):
        # 1. Senior Citizens
        seg_senior = Segment(
            name="Senior Citizens Club",
            description="Elderly residents requiring assistance",
            filter_rules={"age_min": 65},
        )
        persona_senior = compile_segment_persona(seg_senior)
        self.assertIn("Senior", persona_senior["persona_type"])
        self.assertEqual(persona_senior["recommended_tone"], "empathetic")
        self.assertIn("helpline", persona_senior["key_focus"].lower())

        # 2. Youth
        seg_youth = Segment(
            name="Youth Action Volunteers",
            description="Young volunteers across the district",
            filter_rules={"age_max": 25},
        )
        persona_youth = compile_segment_persona(seg_youth)
        self.assertIn("Youth", persona_youth["persona_type"])
        self.assertEqual(persona_youth["recommended_tone"], "friendly")

        # 3. Farmers / Agriculture
        seg_farmer = Segment(
            name="Kisan Welfare Association",
            description="Rural farmers and agriculture workers",
            filter_rules={"occupation": "farmer"},
        )
        persona_farmer = compile_segment_persona(seg_farmer)
        self.assertIn("Rural", persona_farmer["persona_type"])

        # 4. Urban Commuters
        seg_urban = Segment(
            name="Urban Metro Commuters",
            description="City transit commuters",
            filter_rules={"location_type": "urban"},
        )
        persona_urban = compile_segment_persona(seg_urban)
        self.assertIn("Urban", persona_urban["persona_type"])

        # 5. Default General Public
        seg_gen = Segment(
            name="District General Residents",
            description="General public recipients",
            filter_rules={},
        )
        persona_gen = compile_segment_persona(seg_gen)
        self.assertEqual(persona_gen["persona_type"], "General Public")

    def test_compute_variant_hash_determinism(self):
        h1 = compute_variant_hash("Title", "Body content", "Click here")
        h2 = compute_variant_hash("Title", "Body content", "Click here")
        h3 = compute_variant_hash("Title", "Body content changed", "Click here")

        self.assertEqual(h1, h2)
        self.assertNotEqual(h1, h3)
        self.assertEqual(len(h1), 64)


class TestPersonalizationIntegration(unittest.TestCase):
    """Integration tests for variant generation, lifecycle, Phase 1A approval gating, and preview simulation."""

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
            email="admin@personalize.gov.in",
            hashed_password=get_password_hash("Secret123!"),
            full_name="Admin Officer",
            role_id=1,
            organization="Disaster Mgmt Dept",
            is_active=True,
        )
        self.manager_user = User(
            email="manager@personalize.gov.in",
            hashed_password=get_password_hash("Secret123!"),
            full_name="Campaign Manager Officer",
            role_id=2,
            organization="Disaster Mgmt Dept",
            is_active=True,
        )
        self.comm_user = User(
            email="comm@personalize.gov.in",
            hashed_password=get_password_hash("Secret123!"),
            full_name="Communications Staff",
            role_id=3,
            organization="Disaster Mgmt Dept",
            is_active=True,
        )
        self.foreign_user = User(
            email="foreign@otherdept.gov.in",
            hashed_password=get_password_hash("Secret123!"),
            full_name="Foreign Officer",
            role_id=2,
            organization="Another Department",
            is_active=True,
        )
        self.db.add_all([self.admin_user, self.manager_user, self.comm_user, self.foreign_user])
        self.db.commit()

        # Campaign & Segments
        self.campaign = Campaign(
            name="Flood Alert Campaign 2026",
            campaign_type="Emergency Alert",
            objective="Deliver personalized flood warnings",
            status="Draft",
            created_by=self.manager_user.id,
        )
        self.db.add(self.campaign)
        self.db.commit()

        self.seg_senior = Segment(
            name="Vulnerable Senior Citizens",
            description="Elderly residents requiring door-to-door support",
            filter_rules={"age_min": 65},
            created_by=self.manager_user.id,
        )
        self.seg_youth = Segment(
            name="Youth Volunteers Squad",
            description="Active youth volunteers",
            filter_rules={"age_max": 25},
            created_by=self.manager_user.id,
        )
        self.db.add_all([self.seg_senior, self.seg_youth])
        self.db.commit()

        # Recipient
        self.member_senior = AudienceMember(
            name="Ramesh Sharma",
            email="ramesh.sharma@example.com",
            phone="+919876543210",
            city="Chennai",
            preferred_language="en",
        )
        self.db.add(self.member_senior)
        self.db.commit()

        # Content Asset with placeholders and helplines
        self.asset = ContentAsset(
            campaign_id=self.campaign.id,
            title="Monsoon Waterlogging Alert",
            body="Dear {name}, heavy rains expected in {city}. Call emergency helpline 1077 or 104 immediately for shelter.",
            call_to_action="Contact helpline 1077 now",
            channel="SMS",
            category="Emergency Alert",
            source_language="en",
            review_status="Approved",
            created_by=self.manager_user.id,
        )
        self.db.add(self.asset)
        self.db.commit()

        def override_get_db():
            try:
                yield self.db
            finally:
                pass

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)

        self.admin_token = create_access_token(self.admin_user.id)
        self.manager_token = create_access_token(self.manager_user.id)
        self.comm_token = create_access_token(self.comm_user.id)
        self.foreign_token = create_access_token(self.foreign_user.id)

    def tearDown(self):
        app.dependency_overrides.clear()
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)

    def test_batch_variant_generation_and_factual_preservation(self):
        req = ContentPersonalizeRequest(
            segment_ids=[self.seg_senior.id, self.seg_youth.id],
            channel="SMS",
            language="en",
        )
        res = personalize_content_asset(
            db=self.db,
            asset_id=self.asset.id,
            payload=req,
            current_user=self.manager_user,
        )

        self.assertEqual(res.total_requested, 2)
        self.assertEqual(res.success_count, 2)
        self.assertEqual(res.failure_count, 0)

        # Inspect generated variants in DB
        variants = list_content_variants(
            db=self.db,
            asset_id=self.asset.id,
            current_user=self.manager_user,
        )
        self.assertEqual(len(variants), 2)

        senior_v = next(v for v in variants if v.segment_id == self.seg_senior.id)
        # Check factual anchors preserved
        self.assertIn("1077", senior_v.variant_body)
        self.assertIn("104", senior_v.variant_body)
        self.assertIn("{name}", senior_v.variant_body)
        self.assertIn("{city}", senior_v.variant_body)
        self.assertEqual(senior_v.review_status, "Draft")
        self.assertTrue(len(senior_v.content_version_hash) == 64)

    def test_variant_generation_idempotency_upsert(self):
        req = ContentPersonalizeRequest(
            segment_ids=[self.seg_senior.id],
            channel="SMS",
            language="en",
        )
        # Run first time
        res1 = personalize_content_asset(self.db, self.asset.id, req, self.manager_user)
        self.assertEqual(res1.success_count, 1)

        # Run second time (should update existing variant, not create duplicate)
        res2 = personalize_content_asset(self.db, self.asset.id, req, self.manager_user)
        self.assertEqual(res2.success_count, 1)

        variants = list_content_variants(self.db, self.asset.id, self.manager_user)
        self.assertEqual(len(variants), 1)

    def test_material_edit_resets_approval_and_invalidates_hash(self):
        req = ContentPersonalizeRequest(
            segment_ids=[self.seg_senior.id],
            channel="SMS",
            language="en",
        )
        personalize_content_asset(self.db, self.asset.id, req, self.manager_user)
        v = list_content_variants(self.db, self.asset.id, self.manager_user)[0]
        initial_hash = v.content_version_hash

        # Approve variant
        appr_update = ContentVariantUpdate(review_status="Approved")
        v_appr = update_content_variant(self.db, v.id, appr_update, self.manager_user)
        self.assertEqual(v_appr.review_status, "Approved")
        self.assertEqual(v_appr.reviewed_by, self.manager_user.id)
        self.assertIsNotNone(v_appr.reviewed_at)

        # Material edit: change body text
        edit_update = ContentVariantUpdate(
            variant_body="Updated advisory text for {name} in {city}. Emergency helpline 1077."
        )
        v_edited = update_content_variant(self.db, v.id, edit_update, self.manager_user)
        self.assertEqual(v_edited.review_status, "Draft")
        self.assertIsNone(v_edited.reviewed_by)
        self.assertIsNone(v_edited.reviewed_at)
        self.assertNotEqual(v_edited.content_version_hash, initial_hash)

    def test_variant_approval_blocked_on_critical_compliance_finding(self):
        # Create an active compliance rule with critical severity
        rule = ComplianceRule(
            rule_code="COMP-BW-PANIC",
            name="Ban Panic Words",
            rule_type="banned_word",
            pattern="fatal catastrophe",
            channel="SMS",
            suggested_action="Remove panic phrasing",
            severity="critical",
            is_active=True,
            is_global=True,
            created_by=self.admin_user.id,
        )
        self.db.add(rule)
        self.db.commit()

        # Create variant with critical banned word
        v = ContentVariant(
            campaign_id=self.campaign.id,
            source_content_id=self.asset.id,
            segment_id=self.seg_senior.id,
            language="en",
            channel="SMS",
            variant_title="Warning",
            variant_body="This is a fatal catastrophe for all residents.",
            review_status="Draft",
            content_version_hash=compute_variant_hash("Warning", "This is a fatal catastrophe for all residents.", None),
            created_by=self.manager_user.id,
        )
        self.db.add(v)
        self.db.commit()

        # Attempt to approve variant -> must be rejected with 400
        from fastapi import HTTPException
        with self.assertRaises(HTTPException) as ctx:
            update_content_variant(
                self.db,
                v.id,
                ContentVariantUpdate(review_status="Approved"),
                self.manager_user,
            )
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("critical compliance findings", ctx.exception.detail)

    def test_variant_approval_rbac_restriction(self):
        req = ContentPersonalizeRequest(
            segment_ids=[self.seg_senior.id],
            channel="SMS",
            language="en",
        )
        personalize_content_asset(self.db, self.asset.id, req, self.manager_user)
        v = list_content_variants(self.db, self.asset.id, self.manager_user)[0]

        # Communication Team (non-manager) cannot approve
        from fastapi import HTTPException
        with self.assertRaises(HTTPException) as ctx:
            update_content_variant(
                self.db,
                v.id,
                ContentVariantUpdate(review_status="Approved"),
                self.comm_user,
            )
        self.assertEqual(ctx.exception.status_code, 403)

    def test_recipient_preview_simulation(self):
        req = ContentPersonalizeRequest(
            segment_ids=[self.seg_senior.id],
            channel="SMS",
            language="en",
        )
        personalize_content_asset(self.db, self.asset.id, req, self.manager_user)

        # Simulate recipient preview
        preview_req = RecipientPreviewRequest(
            recipient_id=self.member_senior.id,
            channel="SMS",
            preferred_language="en",
        )
        res = preview_recipient_message(
            db=self.db,
            asset_id=self.asset.id,
            payload=preview_req,
            current_user=self.manager_user,
        )

        self.assertEqual(res.recipient_id, self.member_senior.id)
        self.assertEqual(res.recipient_name, "Ramesh Sharma")
        self.assertTrue(res.is_simulation)
        # Check substituted values
        self.assertIn("Ramesh Sharma", res.preview_body)
        self.assertIn("Chennai", res.preview_body)
        self.assertNotIn("{name}", res.preview_body)
        self.assertNotIn("{city}", res.preview_body)

    def test_multi_tenant_isolation_enforcement(self):
        # Foreign user attempts to generate variants for asset belonging to another org
        from fastapi import HTTPException
        req = ContentPersonalizeRequest(
            segment_ids=[self.seg_senior.id],
            channel="SMS",
            language="en",
        )
        with self.assertRaises(HTTPException) as ctx:
            personalize_content_asset(
                db=self.db,
                asset_id=self.asset.id,
                payload=req,
                current_user=self.foreign_user,
            )
        self.assertEqual(ctx.exception.status_code, 403)


    # -----------------------------------------------------------------------
    # API Router Endpoints Verification via TestClient
    # -----------------------------------------------------------------------

    def test_api_personalize_generate_and_list(self):
        headers = {"Authorization": f"Bearer {self.manager_token}"}
        payload = {
            "segment_ids": [self.seg_senior.id, self.seg_youth.id],
            "channel": "SMS",
            "language": "en",
        }
        res = self.client.post(f"/content/{self.asset.id}/personalize", json=payload, headers=headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["total_requested"], 2)
        self.assertEqual(data["success_count"], 2)

        # List variants endpoint
        res_list = self.client.get(f"/content/{self.asset.id}/personalize/variants", headers=headers)
        self.assertEqual(res_list.status_code, 200)
        variants = res_list.json()
        self.assertEqual(len(variants), 2)

    def test_api_recipient_preview_simulation_get_and_post(self):
        headers = {"Authorization": f"Bearer {self.manager_token}"}
        # First generate
        self.client.post(
            f"/content/{self.asset.id}/personalize",
            json={"segment_ids": [self.seg_senior.id], "channel": "SMS"},
            headers=headers,
        )

        # POST preview
        res_post = self.client.post(
            f"/content/{self.asset.id}/personalize/preview-recipient",
            json={"recipient_id": self.member_senior.id, "channel": "SMS"},
            headers=headers,
        )
        self.assertEqual(res_post.status_code, 200)
        data_post = res_post.json()
        self.assertEqual(data_post["recipient_name"], "Ramesh Sharma")
        self.assertTrue(data_post["is_simulation"])

        # GET preview
        res_get = self.client.get(
            f"/content/{self.asset.id}/personalize/preview-recipient?recipient_id={self.member_senior.id}&channel=SMS",
            headers=headers,
        )
        self.assertEqual(res_get.status_code, 200)
        data_get = res_get.json()
        self.assertEqual(data_get["recipient_name"], "Ramesh Sharma")
        self.assertEqual(data_get["preview_body"], data_post["preview_body"])

    def test_api_delete_content_variant(self):
        headers = {"Authorization": f"Bearer {self.manager_token}"}
        self.client.post(
            f"/content/{self.asset.id}/personalize",
            json={"segment_ids": [self.seg_senior.id]},
            headers=headers,
        )
        v_list = self.client.get(f"/content/{self.asset.id}/personalize/variants", headers=headers).json()
        self.assertEqual(len(v_list), 1)
        v_id = v_list[0]["id"]

        # Delete variant
        res_del = self.client.delete(f"/content/variants/{v_id}", headers=headers)
        self.assertEqual(res_del.status_code, 200)

        # Confirm deleted
        v_list_after = self.client.get(f"/content/{self.asset.id}/personalize/variants", headers=headers).json()
        self.assertEqual(len(v_list_after), 0)

    def test_recipient_preview_fallback_to_root_asset(self):
        # Preview for a recipient with no segment or unmatched segment falls back to master asset
        preview_req = RecipientPreviewRequest(
            recipient_id=self.member_senior.id,
            channel="SMS",
        )
        res = preview_recipient_message(
            db=self.db,
            asset_id=self.asset.id,
            payload=preview_req,
            current_user=self.manager_user,
        )
        self.assertTrue(res.is_fallback)
        self.assertIsNone(res.used_variant_id)
        self.assertIn("Ramesh Sharma", res.preview_body)

    def test_delete_variant_cross_officer_forbidden(self):
        # Create a variant authored by manager
        v = ContentVariant(
            campaign_id=self.campaign.id,
            source_content_id=self.asset.id,
            segment_id=self.seg_senior.id,
            language="en",
            channel="SMS",
            variant_title="Senior Alert",
            variant_body="Senior citizen advisory for {name} in {city}. Helpline 1077.",
            review_status="Draft",
            content_version_hash=compute_variant_hash("Senior Alert", "Senior citizen advisory for {name} in {city}. Helpline 1077.", None),
            created_by=self.manager_user.id,
        )
        self.db.add(v)
        self.db.commit()

        # Comm user is not admin and didn't create the variant -> 403 Forbidden
        from fastapi import HTTPException
        with self.assertRaises(HTTPException) as ctx:
            delete_content_variant(
                db=self.db,
                variant_id=v.id,
                current_user=self.comm_user,
            )
        self.assertEqual(ctx.exception.status_code, 403)

    def test_distribution_staging_resolves_approved_segment_variant(self):
        from app.services.distribution.job_service import create_distribution_job
        from app.services.quality_service import compute_content_version_hash
        from app.models.content_quality import ContentQualityAssessment

        self.campaign.status = "Approved"
        self.campaign.channels = ["SMS"]
        self.campaign.segments = [self.seg_senior]
        self.member_senior.age = 70
        self.member_senior.consent_status = True

        # Phase 1A security invariant: ensure content asset has valid quality assessment
        assessment = ContentQualityAssessment(
            content_asset_id=self.asset.id,
            content_version_hash=compute_content_version_hash(self.asset.title, self.asset.body, self.asset.call_to_action),
            overall_score=95.0,
            status="completed",
            dimension_scores={},
            critical_issues_count=0,
            created_by=self.manager_user.id,
        )
        self.db.add(assessment)
        self.db.commit()

        # Create variant for senior segment
        v = ContentVariant(
            campaign_id=self.campaign.id,
            source_content_id=self.asset.id,
            segment_id=self.seg_senior.id,
            language="en",
            channel="SMS",
            variant_title="Senior Alert",
            variant_body="Senior door-to-door advisory for {name} in {city}. Helpline 1077.",
            review_status="Draft",
            content_version_hash=compute_variant_hash("Senior Alert", "Senior door-to-door advisory for {name} in {city}. Helpline 1077.", None),
            created_by=self.manager_user.id,
        )
        self.db.add(v)
        self.db.commit()

        # Approve variant via update_content_variant (which automatically assesses and links assessment_id)
        update_content_variant(self.db, v.id, ContentVariantUpdate(review_status="Approved"), self.manager_user)
        self.db.refresh(v)
        self.assertEqual(v.review_status, "Approved")
        self.assertIsNotNone(v.assessment_id)

        # Create distribution job
        job = create_distribution_job(
            db=self.db,
            campaign_id=self.campaign.id,
            channel="SMS",
            current_user=self.manager_user,
        )

        self.assertEqual(job.status, "queued")
        self.assertEqual(len(job.delivery_records), 1)
        record = job.delivery_records[0]
        self.assertEqual(record.delivery_status, "pending")
        # Verify rendered content came from segment variant, not root asset
        self.assertIn("Senior door-to-door advisory for Ramesh Sharma in Chennai.", record.rendered_content)
        self.assertIn("1077", record.rendered_content)

    def test_variant_cannot_be_approved_with_parent_assessment(self):
        from app.services.quality_service import validate_variant_approval_readiness, compute_content_version_hash
        from app.models.content_quality import ContentQualityAssessment

        # Create assessment for parent asset
        parent_assessment = ContentQualityAssessment(
            content_asset_id=self.asset.id,
            content_version_hash=compute_content_version_hash(self.asset.title, self.asset.body, self.asset.call_to_action),
            overall_score=95.0,
            status="completed",
            dimension_scores={},
            critical_issues_count=0,
            created_by=self.manager_user.id,
        )
        self.db.add(parent_assessment)
        self.db.commit()

        # Create variant that maliciously references parent's assessment
        v = ContentVariant(
            campaign_id=self.campaign.id,
            source_content_id=self.asset.id,
            segment_id=self.seg_senior.id,
            language="en",
            channel="SMS",
            variant_title="Senior Advisory",
            variant_body="Senior advisory content for {name} in {city}. Helpline 1077.",
            review_status="Draft",
            assessment_id=parent_assessment.id,
            content_version_hash=compute_variant_hash("Senior Advisory", "Senior advisory content for {name} in {city}. Helpline 1077.", None),
            created_by=self.manager_user.id,
        )
        self.db.add(v)
        self.db.commit()

        # Validation must reject parent assessment
        is_ready, err_code, reasons = validate_variant_approval_readiness(self.db, v)
        self.assertFalse(is_ready)
        self.assertEqual(err_code, "PARENT_ASSESSMENT_NOT_APPLICABLE")

    def test_stale_variant_hash_blocks_distribution(self):
        from app.services.distribution.job_service import create_distribution_job
        from app.services.quality_service import compute_content_version_hash
        from app.models.content_quality import ContentQualityAssessment

        self.campaign.status = "Approved"
        self.campaign.channels = ["SMS"]
        self.campaign.segments = [self.seg_senior]
        self.member_senior.age = 70
        self.member_senior.consent_status = True

        parent_assessment = ContentQualityAssessment(
            content_asset_id=self.asset.id,
            content_version_hash=compute_content_version_hash(self.asset.title, self.asset.body, self.asset.call_to_action),
            overall_score=95.0,
            status="completed",
            dimension_scores={},
            critical_issues_count=0,
            created_by=self.manager_user.id,
        )
        self.db.add(parent_assessment)
        self.db.commit()

        # Create approved variant
        v = ContentVariant(
            campaign_id=self.campaign.id,
            source_content_id=self.asset.id,
            segment_id=self.seg_senior.id,
            language="en",
            channel="SMS",
            variant_title="Senior Alert",
            variant_body="Senior advisory for {name} in {city}. Helpline 1077.",
            review_status="Draft",
            content_version_hash=compute_variant_hash("Senior Alert", "Senior advisory for {name} in {city}. Helpline 1077.", None),
            created_by=self.manager_user.id,
        )
        self.db.add(v)
        self.db.commit()
        update_content_variant(self.db, v.id, ContentVariantUpdate(review_status="Approved"), self.manager_user)
        self.db.refresh(v)

        # Tamper with variant body directly in DB to simulate post-approval edit (stale hash)
        v.variant_body = "Tampered text without re-evaluation."
        self.db.commit()

        # Distribution job should exclude stale variant and fall back to root asset
        job = create_distribution_job(self.db, self.campaign.id, "SMS", self.manager_user)
        record = job.delivery_records[0]
        self.assertNotIn("Tampered text", record.rendered_content)

    def test_api_evaluate_variant_endpoint(self):
        headers = {"Authorization": f"Bearer {self.manager_token}"}
        v = ContentVariant(
            campaign_id=self.campaign.id,
            source_content_id=self.asset.id,
            segment_id=self.seg_senior.id,
            language="en",
            channel="SMS",
            variant_title="Senior Alert",
            variant_body="Advisory for {name} in {city}. Helpline 1077.",
            review_status="Draft",
            content_version_hash=compute_variant_hash("Senior Alert", "Advisory for {name} in {city}. Helpline 1077.", None),
            created_by=self.manager_user.id,
        )
        self.db.add(v)
        self.db.commit()

        res = self.client.post(f"/content/variants/{v.id}/quality/evaluate", headers=headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["content_asset_id"], self.asset.id)
        self.assertEqual(data["critical_issues_count"], 0)
        self.assertFalse(data["is_outdated"])

        # DB variant now linked to assessment
        self.db.refresh(v)
        self.assertIsNotNone(v.assessment_id)
        self.assertEqual(v.assessment_id, data["id"])




if __name__ == "__main__":
    unittest.main()
