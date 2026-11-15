"""Automated Unit and Integration Tests for Milestone 2, Task 12: End-to-End Content Pipeline.

Tests the full orchestration flow:
Generate -> Translate -> Personalize -> Tone Optimize -> Review
Includes partial execution, resumption, idempotency, RBAC, and error recovery.
"""

import unittest
from unittest.mock import patch, AsyncMock
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.main import app
from app.db.base import Base
from app.db.session import get_db
from app.core.security import create_access_token, get_password_hash
from app.models.user import User, Role
from app.models.campaign import Campaign
from app.models.segment import Segment
from app.models.content_asset import ContentAsset
from app.models.content_variant import ContentVariant
from app.models.pipeline_run import ContentPipelineRun
from app.schemas.pipeline import ContentPipelineRequest, ContentPipelineResumeRequest


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


class TestContentPipelineIntegration(unittest.TestCase):
    """Integration test suite for the Task 12 End-to-End Content Pipeline."""

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
            email="admin@pipeline.gov.in",
            hashed_password=get_password_hash("Secret123!"),
            full_name="Admin Officer",
            role_id=1,
            organization="Disaster Mgmt Dept",
            is_active=True,
        )
        self.manager_user = User(
            email="manager@pipeline.gov.in",
            hashed_password=get_password_hash("Secret123!"),
            full_name="Campaign Manager Officer",
            role_id=2,
            organization="Disaster Mgmt Dept",
            is_active=True,
        )
        self.comm_user = User(
            email="comm@pipeline.gov.in",
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
            organization="Other Department",
            is_active=True,
        )
        self.db.add_all([self.admin_user, self.manager_user, self.comm_user, self.foreign_user])
        self.db.commit()

        # Campaign & Segments
        self.campaign = Campaign(
            name="Flood Preparedness 2026",
            campaign_type="Emergency Alert",
            objective="Alert residents about monsoon waterlogging and emergency helplines",
            priority="High",
            status="Draft",
            channels=["SMS", "Email"],
            created_by=self.manager_user.id,
        )
        self.db.add(self.campaign)
        self.db.commit()

        self.seg_seniors = Segment(
            name="Elderly Citizens",
            description="Elderly citizens requiring assistance",
            filter_rules={"age_min": 65},
            created_by=self.manager_user.id,
        )
        self.seg_volunteers = Segment(
            name="Emergency Volunteers",
            description="Active youth volunteers",
            filter_rules={"age_max": 30},
            created_by=self.manager_user.id,
        )
        self.db.add_all([self.seg_seniors, self.seg_volunteers])
        self.db.commit()

        self.campaign.segments = [self.seg_seniors, self.seg_volunteers]
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

    def test_successful_complete_pipeline_execution(self):
        """Tests complete 5-stage pipeline run: Generate -> Translate -> Personalize -> Tone Optimize -> Review."""
        headers = {"Authorization": f"Bearer {self.manager_token}"}
        payload = {
            "topic": "Flood Preparedness 2026",
            "objective": "Alert residents and provide emergency assistance numbers",
            "category": "Emergency Alert",
            "channels": ["SMS", "Email"],
            "source_language": "en",
            "target_languages": ["hi", "ta"],
            "segment_ids": [self.seg_seniors.id, self.seg_volunteers.id],
            "target_tone": "Friendly",
            "tone_instruction": "Friendlier & Reassuring",
            "facts": ["Helpline 1077 is active 24x7", "Shelters open at Municipal Hall"],
            "constraints": ["Keep SMS brief"],
            "submit_for_review": True,
            "idempotency_key": "pipe-run-test-001",
        }

        res = self.client.post(f"/campaigns/{self.campaign.id}/content/pipeline", json=payload, headers=headers)
        self.assertEqual(res.status_code, 200, res.text)
        data = res.json()

        self.assertEqual(data["campaign_id"], self.campaign.id)
        self.assertEqual(data["status"], "completed")
        self.assertEqual(data["current_stage"], "completed")
        self.assertEqual(data["completed_stages"], 5)
        self.assertEqual(data["total_stages"], 5)
        self.assertEqual(data["progress_percent"], 100.0)
        self.assertIsNone(data["error_message"])

        # Check stage outputs
        stage_outputs = data["stage_outputs"]
        self.assertIn("generate", stage_outputs)
        self.assertIn("translate", stage_outputs)
        self.assertIn("personalize", stage_outputs)
        self.assertIn("tone_optimize", stage_outputs)
        self.assertIn("review", stage_outputs)

        self.assertEqual(stage_outputs["generate"]["status"], "completed")
        self.assertEqual(stage_outputs["translate"]["status"], "completed")
        self.assertEqual(stage_outputs["personalize"]["status"], "completed")
        self.assertEqual(stage_outputs["tone_optimize"]["status"], "completed")
        self.assertEqual(stage_outputs["review"]["status"], "completed")

        # Verify generated ContentAssets in DB
        assets = self.db.query(ContentAsset).filter(ContentAsset.campaign_id == self.campaign.id).all()
        # Should have root assets (SMS, Email) + translations (Hindi, Tamil for each)
        self.assertGreaterEqual(len(assets), 2)
        for a in assets:
            self.assertEqual(a.review_status, "In Review")

        # Verify demographic ContentVariants in DB
        variants = self.db.query(ContentVariant).filter(ContentVariant.campaign_id == self.campaign.id).all()
        self.assertGreaterEqual(len(variants), 2)
        for v in variants:
            self.assertEqual(v.review_status, "In_Review")
            self.assertIsNotNone(v.assessment_id)

    def test_idempotency_key_returns_existing_completed_run(self):
        """Verifies duplicate requests with identical idempotency_key return existing completed run without re-executing."""
        headers = {"Authorization": f"Bearer {self.manager_token}"}
        payload = {
            "topic": "Heatwave Advisory 2026",
            "channels": ["SMS"],
            "target_languages": ["hi"],
            "idempotency_key": "idempotent-key-heatwave-99",
            "submit_for_review": True,
        }

        # Run 1
        res1 = self.client.post(f"/campaigns/{self.campaign.id}/content/pipeline", json=payload, headers=headers)
        self.assertEqual(res1.status_code, 200)
        run1_data = res1.json()
        run1_id = run1_data["id"]

        # Run 2 with same idempotency key
        res2 = self.client.post(f"/campaigns/{self.campaign.id}/content/pipeline", json=payload, headers=headers)
        self.assertEqual(res2.status_code, 200)
        run2_data = res2.json()

        self.assertEqual(run2_data["id"], run1_id)
        self.assertEqual(run2_data["status"], "completed")

    def test_in_progress_idempotency_conflict_returns_409(self):
        """Verifies an active in_progress pipeline blocks concurrent executions with 409 Conflict."""
        # Create a run in in_progress state
        run = ContentPipelineRun(
            campaign_id=self.campaign.id,
            status="in_progress",
            current_stage="translate",
            idempotency_key="active-key-concurrent-123",
            created_by=self.manager_user.id,
        )
        self.db.add(run)
        self.db.commit()

        headers = {"Authorization": f"Bearer {self.manager_token}"}
        payload = {
            "channels": ["SMS"],
            "idempotency_key": "active-key-concurrent-123",
        }
        res = self.client.post(f"/campaigns/{self.campaign.id}/content/pipeline", json=payload, headers=headers)
        self.assertEqual(res.status_code, 409)
        self.assertIn("currently in progress", res.json()["detail"])

    def test_partial_failure_and_resume_recovery(self):
        """Verifies that if a stage fails, partial work is preserved and resume picks up from failed stage."""
        headers = {"Authorization": f"Bearer {self.manager_token}"}

        # Mock personalize_content_asset in pipeline_service to fail on first attempt
        from app.services import pipeline_service
        original_pers = pipeline_service.personalize_content_asset

        def failing_personalize(*args, **kwargs):
            raise RuntimeError("Simulated segmentation failure in stage 3")

        pipeline_service.personalize_content_asset = failing_personalize

        payload = {
            "topic": "Cyclone Warning",
            "channels": ["SMS"],
            "target_languages": ["ta"],
            "segment_ids": [self.seg_seniors.id],
            "idempotency_key": "resume-key-cyclone-1",
            "submit_for_review": True,
        }

        # Initial run -> should fail at Stage 3 (personalize)
        res1 = self.client.post(f"/campaigns/{self.campaign.id}/content/pipeline", json=payload, headers=headers)
        self.assertEqual(res1.status_code, 500)

        # Restore original function
        pipeline_service.personalize_content_asset = original_pers

        # Check run status in DB
        run = self.db.query(ContentPipelineRun).filter(ContentPipelineRun.idempotency_key == "resume-key-cyclone-1").first()
        self.assertIsNotNone(run)
        self.assertEqual(run.status, "failed")
        self.assertEqual(run.completed_stages, 2)  # Stages 1 & 2 completed
        self.assertIn("Simulated segmentation failure", run.error_message)

        # Assets from Stage 1 & 2 must be preserved
        self.assertGreaterEqual(len(run.generated_asset_ids), 1)

        # Resume the pipeline run
        resume_res = self.client.post(
            f"/campaigns/{self.campaign.id}/content/pipeline/{run.id}/resume",
            json={},
            headers=headers,
        )
        self.assertEqual(resume_res.status_code, 200, resume_res.text)
        resumed_data = resume_res.json()
        self.assertEqual(resumed_data["status"], "completed")
        self.assertEqual(resumed_data["completed_stages"], 5)
        self.assertEqual(resumed_data["progress_percent"], 100.0)

    def test_nonexistent_campaign_returns_404(self):
        """Verifies targeting a nonexistent campaign returns 404."""
        headers = {"Authorization": f"Bearer {self.manager_token}"}
        res = self.client.post("/campaigns/99999/content/pipeline", json={"channels": ["SMS"]}, headers=headers)
        self.assertEqual(res.status_code, 404)

    def test_approved_or_archived_campaign_blocks_pipeline(self):
        """Verifies campaigns in Approved status cannot have content pipelines executed."""
        self.campaign.status = "Approved"
        self.db.commit()

        headers = {"Authorization": f"Bearer {self.manager_token}"}
        res = self.client.post(f"/campaigns/{self.campaign.id}/content/pipeline", json={"channels": ["SMS"]}, headers=headers)
        self.assertEqual(res.status_code, 400)
        self.assertIn("Only Draft or In Review campaigns can be processed", res.json()["detail"])

    def test_unauthorized_user_and_cross_organization_forbidden(self):
        """Verifies Communication Team role (lacking write) and cross-org access are rejected with 403."""
        # 1. Comm team role without write permissions
        comm_headers = {"Authorization": f"Bearer {self.comm_token}"}
        res1 = self.client.post(f"/campaigns/{self.campaign.id}/content/pipeline", json={"channels": ["SMS"]}, headers=comm_headers)
        self.assertEqual(res1.status_code, 403)

        # 2. Foreign organization officer
        foreign_headers = {"Authorization": f"Bearer {self.foreign_token}"}
        res2 = self.client.post(f"/campaigns/{self.campaign.id}/content/pipeline", json={"channels": ["SMS"]}, headers=foreign_headers)
        self.assertEqual(res2.status_code, 403)

    def test_admin_can_execute_pipeline_for_any_campaign(self):
        """Verifies Admin role can trigger pipeline for any campaign."""
        admin_headers = {"Authorization": f"Bearer {self.admin_token}"}
        payload = {
            "topic": "Admin Flood Drill",
            "channels": ["SMS"],
            "submit_for_review": False,
        }
        res = self.client.post(f"/campaigns/{self.campaign.id}/content/pipeline", json=payload, headers=admin_headers)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["status"], "completed")

    def test_get_pipeline_run_status_and_list_runs(self):
        """Verifies GET endpoints for retrieving single run progress and listing historical runs."""
        headers = {"Authorization": f"Bearer {self.manager_token}"}
        payload = {
            "topic": "Dengue Awareness",
            "channels": ["SMS"],
            "submit_for_review": True,
        }
        create_res = self.client.post(f"/campaigns/{self.campaign.id}/content/pipeline", json=payload, headers=headers)
        run_id = create_res.json()["id"]

        # GET single run
        get_res = self.client.get(f"/campaigns/{self.campaign.id}/content/pipeline/{run_id}", headers=headers)
        self.assertEqual(get_res.status_code, 200)
        run_data = get_res.json()
        self.assertEqual(run_data["id"], run_id)
        self.assertEqual(run_data["progress_percent"], 100.0)

        # List runs
        list_res = self.client.get(f"/campaigns/{self.campaign.id}/content/pipeline", headers=headers)
        self.assertEqual(list_res.status_code, 200)
        runs_list = list_res.json()
        self.assertGreaterEqual(len(runs_list), 1)
        self.assertEqual(runs_list[0]["id"], run_id)

    def test_pipeline_preserves_factual_helpline_and_placeholders(self):
        """Verifies factual anchors (1077, 104) and placeholders are strictly preserved through tone optimization."""
        headers = {"Authorization": f"Bearer {self.manager_token}"}
        payload = {
            "topic": "Emergency Helplines",
            "objective": "Provide 1077 and 104 helpline numbers to residents",
            "channels": ["SMS"],
            "target_tone": "Formal",
            "tone_instruction": "More Formal & Official",
            "facts": ["Call 1077 for flood emergency", "Dial 104 for health support"],
            "submit_for_review": True,
        }
        res = self.client.post(f"/campaigns/{self.campaign.id}/content/pipeline", json=payload, headers=headers)
        self.assertEqual(res.status_code, 200)

        asset = self.db.query(ContentAsset).filter(ContentAsset.campaign_id == self.campaign.id).first()
        self.assertIsNotNone(asset)
        # Verify anchors preserved in final body
        self.assertIn("1077", asset.body)
        self.assertIn("104", asset.body)

    def test_invalid_channel_validation(self):
        """Verifies that an unsupported channel is rejected by Pydantic validation."""
        headers = {"Authorization": f"Bearer {self.manager_token}"}
        payload = {
            "channels": ["telepathy_channel"],
        }
        res = self.client.post(f"/campaigns/{self.campaign.id}/content/pipeline", json=payload, headers=headers)
        self.assertEqual(res.status_code, 422)
