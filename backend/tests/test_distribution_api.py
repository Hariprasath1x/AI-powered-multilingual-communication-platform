"""Comprehensive HTTP integration test suite for Task 9 Checkpoint 1: Multichannel Distribution APIs."""

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
from app.models.segment import Segment
from app.models.template import Template
from app.models.content_asset import ContentAsset
from app.models.content_quality import ContentQualityAssessment
from app.models.audience import AudienceMember
from app.models.distribution import DistributionJob, DeliveryRecord
from app.core.security import get_password_hash, create_access_token
from app.services.quality_service import compute_content_version_hash


class TestDistributionAPI(unittest.TestCase):
    """Integration test suite covering Distribution APIs, RBAC, Readiness, JIT Consent, and Mock Delivery."""

    @classmethod
    def setUpClass(cls):
        cls.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        cls.TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=cls.engine)

    def setUp(self):
        Base.metadata.create_all(bind=self.engine)
        self.db = self.TestingSessionLocal()
        roles = seed_default_roles(self.db)
        self.admin_role = roles["Admin"]
        self.manager_role = roles["Campaign Manager"]
        self.comm_role = roles["Communication Team"]

        self.admin_user = User(
            full_name="Director Admin",
            email="director@agency.gov.in",
            hashed_password=get_password_hash("AdminPass123!"),
            role_id=self.admin_role.id,
            is_active=True,
        )
        self.manager_user = User(
            full_name="Manager Maya",
            email="maya@agency.gov.in",
            hashed_password=get_password_hash("ManagerPass123!"),
            role_id=self.manager_role.id,
            is_active=True,
        )
        self.other_manager = User(
            full_name="Manager Other",
            email="other@agency.gov.in",
            hashed_password=get_password_hash("OtherPass123!"),
            role_id=self.manager_role.id,
            is_active=True,
        )
        self.comm_user = User(
            full_name="Comm Specialist",
            email="comm@agency.gov.in",
            hashed_password=get_password_hash("CommPass123!"),
            role_id=self.comm_role.id,
            is_active=True,
        )
        self.db.add_all([self.admin_user, self.manager_user, self.other_manager, self.comm_user])
        self.db.commit()

        # Seed template
        self.template = Template(
            title="Urgent Alert: Monsoons",
            category="Disaster Preparedness",
            body="Dear {name}, high rainfall alert for {city}. Dial 1070 for municipal emergency assistance.",
            created_by=self.manager_user.id,
        )
        self.db.add(self.template)
        self.db.commit()

        # Seed audience members
        self.aud1 = AudienceMember(
            name="Aarav Sharma",
            email="aarav@example.gov.in",
            phone="+919876543210",
            city="Chennai",
            consent_status=True,
        )
        self.aud2 = AudienceMember(
            name="Priya Patel",
            email="priya@example.gov.in",
            phone="+919876543211",
            city="Chennai",
            consent_status=True,
        )
        self.aud_opt_out = AudienceMember(
            name="Revoked Citizen",
            email="optout@example.gov.in",
            phone="+919876543212",
            city="Chennai",
            consent_status=False,  # Explicit opt-out
        )
        self.db.add_all([self.aud1, self.aud2, self.aud_opt_out])
        self.db.commit()

        # Seed Segment
        self.segment = Segment(
            name="Chennai Flood Zone",
            filter_rules={
                "combinator": "AND",
                "rules": [{"field": "city", "operator": "equals", "value": "Chennai"}],
            },
            created_by=self.manager_user.id,
        )
        self.db.add(self.segment)
        self.db.commit()

        # Seed approved campaign
        self.campaign = Campaign(
            name="Monsoon Flood Alert",
            campaign_type="Emergency Alert",
            objective="Notify citizens about flood protocols",
            priority="High",
            status="Approved",
            channels=["Email", "SMS", "WhatsApp", "Voice", "Web"],
            template_id=self.template.id,
            created_by=self.manager_user.id,
        )
        self.campaign.segments = [self.segment]
        self.db.add(self.campaign)
        self.db.commit()
        self.db.refresh(self.campaign)

        # Tokens
        self.admin_token = create_access_token(self.admin_user.id)
        self.manager_token = create_access_token(self.manager_user.id)
        self.other_manager_token = create_access_token(self.other_manager.id)
        self.comm_token = create_access_token(self.comm_user.id)

        # FastApi dependency override
        def override_get_db():
            db = self.TestingSessionLocal()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)

    def tearDown(self):
        self.db.rollback()
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)
        app.dependency_overrides.clear()

    def _headers(self, token: str) -> dict:
        return {"Authorization": f"Bearer {token}"}

    # -------------------------------------------------------------------------
    # 1. Unauthenticated & RBAC Permissions
    # -------------------------------------------------------------------------

    def test_unauthenticated_requests_rejected(self):
        """Unauthenticated requests to distribution endpoints return 401."""
        res = self.client.post("/distribution/jobs", json={"campaign_id": self.campaign.id, "channel": "Email"})
        self.assertEqual(res.status_code, 401)

        res_readiness = self.client.get(f"/distribution/readiness/{self.campaign.id}")
        self.assertEqual(res_readiness.status_code, 401)

    def test_rbac_roles_permissions(self):
        """Communication Team cannot create jobs (403), but can read readiness (200)."""
        # Comm Team cannot create job
        res_create = self.client.post(
            "/distribution/jobs",
            json={"campaign_id": self.campaign.id, "channel": "Email"},
            headers=self._headers(self.comm_token),
        )
        self.assertEqual(res_create.status_code, 403)

        # Comm Team can check readiness
        res_ready = self.client.get(
            f"/distribution/readiness/{self.campaign.id}?channel=Email",
            headers=self._headers(self.comm_token),
        )
        self.assertEqual(res_ready.status_code, 200)
        self.assertTrue(res_ready.json()["is_ready"])

    def test_campaign_manager_ownership_isolation(self):
        """Campaign Manager cannot distribute a campaign created by another user."""
        res = self.client.post(
            "/distribution/jobs",
            json={"campaign_id": self.campaign.id, "channel": "Email"},
            headers=self._headers(self.other_manager_token),
        )
        self.assertEqual(res.status_code, 403)
        self.assertIn("permission", res.json()["detail"].lower())

    # -------------------------------------------------------------------------
    # 2. Campaign Lifecycle & Readiness Safeguards
    # -------------------------------------------------------------------------

    def test_draft_or_in_review_campaign_cannot_be_distributed(self):
        """Campaigns in Draft, In Review, or Rejected status are blocked from distribution."""
        draft_campaign = Campaign(
            name="Draft Polio Notice",
            campaign_type="Awareness",
            status="Draft",
            channels=["Email"],
            template_id=self.template.id,
            created_by=self.manager_user.id,
        )
        draft_campaign.segments = [self.segment]
        self.db.add(draft_campaign)
        self.db.commit()

        # Readiness check indicates not ready
        res_ready = self.client.get(
            f"/distribution/readiness/{draft_campaign.id}?channel=Email",
            headers=self._headers(self.manager_token),
        )
        self.assertEqual(res_ready.status_code, 200)
        self.assertFalse(res_ready.json()["is_ready"])
        self.assertIn("Draft", "; ".join(res_ready.json()["blocking_reasons"]))

        # Creating job fails with HTTP 400
        res_job = self.client.post(
            "/distribution/jobs",
            json={"campaign_id": draft_campaign.id, "channel": "Email"},
            headers=self._headers(self.manager_token),
        )
        self.assertEqual(res_job.status_code, 400)
        self.assertIn("Draft", res_job.json()["detail"])

    def test_unsupported_channel_rejected(self):
        """Attempting distribution across a channel not configured for the campaign is rejected."""
        email_only_campaign = Campaign(
            name="Email Only Announcement",
            campaign_type="Awareness",
            status="Approved",
            channels=["Email"],
            template_id=self.template.id,
            created_by=self.manager_user.id,
        )
        email_only_campaign.segments = [self.segment]
        self.db.add(email_only_campaign)
        self.db.commit()

        # Attempting SMS fails
        res = self.client.post(
            "/distribution/jobs",
            json={"campaign_id": email_only_campaign.id, "channel": "SMS"},
            headers=self._headers(self.manager_token),
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("not configured", res.json()["detail"].lower())

    def test_unapproved_or_outdated_content_blocks_distribution(self):
        """Campaign linked to unapproved or outdated content asset cannot be distributed."""
        asset = ContentAsset(
            title="Cyclone Warning",
            body="Cyclone notice body with emergency 1070 helpline.",
            category="Disaster Preparedness",
            channel="Email",
            review_status="Draft",  # Not approved!
            created_by=self.manager_user.id,
        )
        self.db.add(asset)
        self.db.commit()

        camp = Campaign(
            name="Cyclone Campaign",
            campaign_type="Emergency Alert",
            status="Approved",
            channels=["Email"],
            created_by=self.manager_user.id,
        )
        camp.segments = [self.segment]
        camp.content_assets = [asset]
        self.db.add(camp)
        self.db.commit()

        # Fails because content is Draft
        res = self.client.post(
            "/distribution/jobs",
            json={"campaign_id": camp.id, "channel": "Email"},
            headers=self._headers(self.manager_token),
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("Draft", res.json()["detail"])

    # -------------------------------------------------------------------------
    # 3. Job Creation, Staging, and At-Most-Once Deduplication
    # -------------------------------------------------------------------------

    def test_create_distribution_job_success_and_deduplication(self):
        """Creating a distribution job stages records only for consented, deduplicated members."""
        res = self.client.post(
            "/distribution/jobs",
            json={"campaign_id": self.campaign.id, "channel": "Email"},
            headers=self._headers(self.manager_token),
        )
        self.assertEqual(res.status_code, 201)
        job_data = res.json()
        job_uuid = job_data["job_id"]

        self.assertEqual(job_data["status"], "queued")
        self.assertEqual(job_data["channel"], "Email")
        self.assertEqual(job_data["eligible_recipients"], 2)  # aud1 and aud2 (aud_opt_out excluded!)
        self.assertEqual(job_data["queued_recipients"], 2)

        # Inspect staged delivery records
        res_deliveries = self.client.get(
            f"/distribution/jobs/{job_uuid}/deliveries",
            headers=self._headers(self.manager_token),
        )
        self.assertEqual(res_deliveries.status_code, 200)
        items = res_deliveries.json()["items"]
        self.assertEqual(len(items), 2)
        for it in items:
            self.assertNotIn("recipient_address", it)
            self.assertIn("masked_recipient_address", it)
            self.assertNotIn("aarav@example.gov.in", str(it))
            self.assertNotIn("priya@example.gov.in", str(it))
        masked_addresses = [it["masked_recipient_address"] for it in items]
        self.assertIn("aa***@example.gov.in", masked_addresses)
        self.assertIn("pr***@example.gov.in", masked_addresses)

    # -------------------------------------------------------------------------
    # 4. Mock Delivery Processing Across Channels
    # -------------------------------------------------------------------------

    def test_process_mock_delivery_job_all_channels(self):
        """Testing mock delivery execution across Email, SMS, WhatsApp, Voice, and Web."""
        for ch in ["Email", "SMS", "WhatsApp", "Voice", "Web"]:
            # 1. Create job
            res_create = self.client.post(
                "/distribution/jobs",
                json={"campaign_id": self.campaign.id, "channel": ch},
                headers=self._headers(self.manager_token),
            )
            self.assertEqual(res_create.status_code, 201)
            job_uuid = res_create.json()["job_id"]

            # 2. Trigger mock processing
            res_proc = self.client.post(
                f"/distribution/jobs/{job_uuid}/process",
                headers=self._headers(self.manager_token),
            )
            self.assertEqual(res_proc.status_code, 200)
            processed_data = res_proc.json()

            self.assertEqual(processed_data["status"], "completed")
            self.assertEqual(processed_data["delivered_recipients"], 2)
            self.assertEqual(processed_data["failed_recipients"], 0)

            # 3. Check delivery record status & attempts
            res_records = self.client.get(
                f"/distribution/jobs/{job_uuid}/deliveries",
                headers=self._headers(self.manager_token),
            )
            records = res_records.json()["items"]
            for r in records:
                self.assertEqual(r["delivery_status"], "delivered")
                self.assertIsNotNone(r["provider_reference"])
                self.assertGreaterEqual(len(r["attempts"]), 1)
                self.assertEqual(r["attempts"][0]["attempt_status"], "success")

    # -------------------------------------------------------------------------
    # 5. Just-In-Time (JIT) Consent Revocation Protection
    # -------------------------------------------------------------------------

    def test_jit_consent_revocation_skips_dispatch(self):
        """Recipient revoking consent between job creation and processing is skipped at runtime."""
        # Create job
        res_create = self.client.post(
            "/distribution/jobs",
            json={"campaign_id": self.campaign.id, "channel": "Email"},
            headers=self._headers(self.manager_token),
        )
        job_uuid = res_create.json()["job_id"]

        # Audience member 1 revokes consent AFTER job was staged
        member1 = self.db.get(AudienceMember, self.aud1.id)
        member1.consent_status = False
        self.db.commit()

        # Trigger processing
        res_proc = self.client.post(
            f"/distribution/jobs/{job_uuid}/process",
            headers=self._headers(self.manager_token),
        )
        self.assertEqual(res_proc.status_code, 200)
        data = res_proc.json()

        # 1 delivered (priya), 1 skipped due to revoked consent (aarav)
        self.assertEqual(data["delivered_recipients"], 1)
        self.assertEqual(data["skipped_recipients"], 1)

        # Check records
        res_deliv = self.client.get(
            f"/distribution/jobs/{job_uuid}/deliveries",
            headers=self._headers(self.manager_token),
        )
        records = res_deliv.json()["items"]
        aarav_rec = next(r for r in records if r["audience_member_id"] == self.aud1.id)
        self.assertEqual(aarav_rec["delivery_status"], "skipped_consent")
        self.assertEqual(aarav_rec["error_code"], "CONSENT_WITHDRAWN_POST_JOB")

    # -------------------------------------------------------------------------
    # 6. Retry Failed Deliveries and Idempotency
    # -------------------------------------------------------------------------

    def test_retry_failed_records_without_duplicating_delivered(self):
        """Retrying a job only re-dispatches failed records and preserves delivered records."""
        # Add a temporary failing recipient
        failing_member = AudienceMember(
            name="Temporary Busy",
            email="fail_temp@example.gov.in",
            phone="+919876543219",
            city="Chennai",
            consent_status=True,
        )
        self.db.add(failing_member)
        self.db.commit()

        # Create job
        res_create = self.client.post(
            "/distribution/jobs",
            json={"campaign_id": self.campaign.id, "channel": "Email"},
            headers=self._headers(self.manager_token),
        )
        job_uuid = res_create.json()["job_id"]

        # Process job -> 2 delivered, 1 retrying/failed
        res_proc = self.client.post(
            f"/distribution/jobs/{job_uuid}/process",
            headers=self._headers(self.manager_token),
        )
        self.assertEqual(res_proc.status_code, 200)

        # Check deliveries
        res_records = self.client.get(
            f"/distribution/jobs/{job_uuid}/deliveries",
            headers=self._headers(self.manager_token),
        )
        items = res_records.json()["items"]
        fail_rec = next(it for it in items if it["audience_member_id"] == failing_member.id)
        self.assertIn(fail_rec["delivery_status"], ["retrying", "failed"])

        # Change recipient email to a succeeding one to simulate issue resolution
        db_rec = self.db.get(DeliveryRecord, fail_rec["id"])
        db_rec.recipient_address = "fixed@example.gov.in"
        db_rec.delivery_status = "failed"
        self.db.commit()

        # Trigger retry
        res_retry = self.client.post(
            f"/distribution/jobs/{job_uuid}/retry",
            headers=self._headers(self.manager_token),
        )
        self.assertEqual(res_retry.status_code, 200)
        retry_data = res_retry.json()

        # Now all 3 are delivered!
        self.assertEqual(retry_data["delivered_recipients"], 3)
        self.assertEqual(retry_data["failed_recipients"], 0)

        # Confirm Aarav and Priya were not re-dispatched with extra attempts
        res_final = self.client.get(
            f"/distribution/jobs/{job_uuid}/deliveries",
            headers=self._headers(self.manager_token),
        )
        final_items = res_final.json()["items"]
        for item in final_items:
            self.assertEqual(item["delivery_status"], "delivered")
            if item["audience_member_id"] != failing_member.id:
                self.assertEqual(item["attempt_count"], 1)

    # -------------------------------------------------------------------------
    # 7. Job Cancellation
    # -------------------------------------------------------------------------

    def test_cancel_distribution_job(self):
        """Cancelling a queued job transitions job and pending records to cancelled."""
        res_create = self.client.post(
            "/distribution/jobs",
            json={"campaign_id": self.campaign.id, "channel": "Email"},
            headers=self._headers(self.manager_token),
        )
        job_uuid = res_create.json()["job_id"]

        # Cancel job
        res_cancel = self.client.post(
            f"/distribution/jobs/{job_uuid}/cancel",
            headers=self._headers(self.manager_token),
        )
        self.assertEqual(res_cancel.status_code, 200)
        self.assertEqual(res_cancel.json()["status"], "cancelled")

        # Verify records are cancelled
        res_deliv = self.client.get(
            f"/distribution/jobs/{job_uuid}/deliveries",
            headers=self._headers(self.manager_token),
        )
        records = res_deliv.json()["items"]
        for r in records:
            self.assertEqual(r["delivery_status"], "cancelled")

    # -------------------------------------------------------------------------
    # 8. Checkpoint 2 Hardening: Concurrency, Idempotency, JIT & Privacy
    # -------------------------------------------------------------------------

    def test_concurrent_duplicate_job_creation_conflict(self):
        """Creating an active job for same campaign and channel when one is already queued raises 409 Conflict."""
        res1 = self.client.post(
            "/distribution/jobs",
            json={"campaign_id": self.campaign.id, "channel": "Email"},
            headers=self._headers(self.manager_token),
        )
        self.assertEqual(res1.status_code, 201)

        # Attempt to create duplicate active job for the same campaign and channel
        res2 = self.client.post(
            "/distribution/jobs",
            json={"campaign_id": self.campaign.id, "channel": "Email"},
            headers=self._headers(self.manager_token),
        )
        self.assertEqual(res2.status_code, 409)
        self.assertIn("active distribution job", res2.json()["detail"].lower())

    def test_concurrent_job_processing_conflict(self):
        """Attempting to process a job that is already in 'processing' state raises 409 Conflict."""
        res_create = self.client.post(
            "/distribution/jobs",
            json={"campaign_id": self.campaign.id, "channel": "Email"},
            headers=self._headers(self.manager_token),
        )
        job_uuid = res_create.json()["job_id"]

        # Directly set the job status in DB to 'processing'
        job = self.db.query(DistributionJob).filter(DistributionJob.job_id == job_uuid).first()
        job.status = "processing"
        self.db.commit()

        # Call /process on actively processing job
        res_proc = self.client.post(
            f"/distribution/jobs/{job_uuid}/process",
            headers=self._headers(self.manager_token),
        )
        self.assertEqual(res_proc.status_code, 409)
        self.assertIn("already actively processing", res_proc.json()["detail"].lower())

    def test_processing_cancelled_job_rejected(self):
        """Attempting to process a cancelled job raises 400 Bad Request."""
        res_create = self.client.post(
            "/distribution/jobs",
            json={"campaign_id": self.campaign.id, "channel": "Email"},
            headers=self._headers(self.manager_token),
        )
        job_uuid = res_create.json()["job_id"]

        # Cancel it
        self.client.post(
            f"/distribution/jobs/{job_uuid}/cancel",
            headers=self._headers(self.manager_token),
        )

        # Try to process cancelled job
        res_proc = self.client.post(
            f"/distribution/jobs/{job_uuid}/process",
            headers=self._headers(self.manager_token),
        )
        self.assertEqual(res_proc.status_code, 400)
        self.assertIn("cancelled", res_proc.json()["detail"].lower())

    def test_cancelling_completed_or_cancelled_job_rejected(self):
        """Attempting to cancel an already completed or cancelled job raises 400 Bad Request."""
        res_create = self.client.post(
            "/distribution/jobs",
            json={"campaign_id": self.campaign.id, "channel": "Email"},
            headers=self._headers(self.manager_token),
        )
        job_uuid = res_create.json()["job_id"]

        # Process to completion
        self.client.post(
            f"/distribution/jobs/{job_uuid}/process",
            headers=self._headers(self.manager_token),
        )

        # Attempt to cancel completed job
        res_cancel = self.client.post(
            f"/distribution/jobs/{job_uuid}/cancel",
            headers=self._headers(self.manager_token),
        )
        self.assertEqual(res_cancel.status_code, 400)
        self.assertIn("completed", res_cancel.json()["detail"].lower())

    def test_jit_recipient_deleted_prior_to_dispatch(self):
        """Recipient deleted from database between staging and dispatch fails with RECIPIENT_DELETED."""
        res_create = self.client.post(
            "/distribution/jobs",
            json={"campaign_id": self.campaign.id, "channel": "Email"},
            headers=self._headers(self.manager_token),
        )
        job_uuid = res_create.json()["job_id"]

        # Delete aud1 from database directly
        member1 = self.db.get(AudienceMember, self.aud1.id)
        self.db.delete(member1)
        self.db.commit()

        # Process job
        res_proc = self.client.post(
            f"/distribution/jobs/{job_uuid}/process",
            headers=self._headers(self.manager_token),
        )
        self.assertEqual(res_proc.status_code, 200)
        data = res_proc.json()
        self.assertEqual(data["delivered_recipients"], 1)
        self.assertEqual(data["failed_recipients"], 1)

        # Check delivery record
        res_deliv = self.client.get(
            f"/distribution/jobs/{job_uuid}/deliveries",
            headers=self._headers(self.manager_token),
        )
        records = res_deliv.json()["items"]
        deleted_rec = next(r for r in records if r["audience_member_id"] == self.aud1.id)
        self.assertEqual(deleted_rec["delivery_status"], "failed")
        self.assertEqual(deleted_rec["error_code"], "RECIPIENT_DELETED")

    def test_jit_unconfirmed_consent_skipped(self):
        """Recipient whose consent is reset to None (unconfirmed) prior to dispatch is skipped."""
        res_create = self.client.post(
            "/distribution/jobs",
            json={"campaign_id": self.campaign.id, "channel": "Email"},
            headers=self._headers(self.manager_token),
        )
        job_uuid = res_create.json()["job_id"]

        # Reset aud2 consent to None (unconfirmed)
        member2 = self.db.get(AudienceMember, self.aud2.id)
        member2.consent_status = None
        self.db.commit()

        # Process job
        res_proc = self.client.post(
            f"/distribution/jobs/{job_uuid}/process",
            headers=self._headers(self.manager_token),
        )
        self.assertEqual(res_proc.status_code, 200)
        data = res_proc.json()
        self.assertEqual(data["delivered_recipients"], 1)
        self.assertEqual(data["skipped_recipients"], 1)

        res_deliv = self.client.get(
            f"/distribution/jobs/{job_uuid}/deliveries",
            headers=self._headers(self.manager_token),
        )
        records = res_deliv.json()["items"]
        unconfirmed_rec = next(r for r in records if r["audience_member_id"] == self.aud2.id)
        self.assertEqual(unconfirmed_rec["delivery_status"], "skipped_consent")
        self.assertEqual(unconfirmed_rec["error_code"], "CONSENT_UNCONFIRMED_POST_JOB")

    def test_permanent_error_non_retryable_exclusion(self):
        """Non-retryable permanent failures cannot be retried."""
        # Create job with recipient that triggers permanent failure
        perm_fail_member = AudienceMember(
            name="Permanent Fail Citizen",
            email="fail_perm@example.gov.in",
            phone="+919876543299",
            city="Chennai",
            consent_status=True,
        )
        self.db.add(perm_fail_member)
        self.db.commit()

        res_create = self.client.post(
            "/distribution/jobs",
            json={"campaign_id": self.campaign.id, "channel": "Email"},
            headers=self._headers(self.manager_token),
        )
        job_uuid = res_create.json()["job_id"]

        # Process job -> 2 delivered, 1 permanent failure
        self.client.post(
            f"/distribution/jobs/{job_uuid}/process",
            headers=self._headers(self.manager_token),
        )

        # Inspect failure record
        res_deliv = self.client.get(
            f"/distribution/jobs/{job_uuid}/deliveries",
            headers=self._headers(self.manager_token),
        )
        records = res_deliv.json()["items"]
        fail_rec = next(r for r in records if r["audience_member_id"] == perm_fail_member.id)
        self.assertEqual(fail_rec["delivery_status"], "failed")
        self.assertEqual(fail_rec["error_code"], "RECIPIENT_MAILBOX_NOT_FOUND")

        # Attempt to retry -> should fail with 400 since only non-retryable error exists
        res_retry = self.client.post(
            f"/distribution/jobs/{job_uuid}/retry",
            headers=self._headers(self.manager_token),
        )
        self.assertEqual(res_retry.status_code, 400)
        self.assertIn("no eligible failed records", res_retry.json()["detail"].lower())

    def test_retry_cancelled_job_rejected(self):
        """Attempting to retry a cancelled job raises 400 Bad Request."""
        res_create = self.client.post(
            "/distribution/jobs",
            json={"campaign_id": self.campaign.id, "channel": "Email"},
            headers=self._headers(self.manager_token),
        )
        job_uuid = res_create.json()["job_id"]

        self.client.post(
            f"/distribution/jobs/{job_uuid}/cancel",
            headers=self._headers(self.manager_token),
        )

        res_retry = self.client.post(
            f"/distribution/jobs/{job_uuid}/retry",
            headers=self._headers(self.manager_token),
        )
        self.assertEqual(res_retry.status_code, 400)
        self.assertIn("cancelled", res_retry.json()["detail"].lower())

    def test_privacy_masking_in_delivery_records(self):
        """Recipient addresses are masked in API responses for privacy protection, and raw address is omitted."""
        res_create = self.client.post(
            "/distribution/jobs",
            json={"campaign_id": self.campaign.id, "channel": "Email"},
            headers=self._headers(self.manager_token),
        )
        job_uuid = res_create.json()["job_id"]

        res_deliv = self.client.get(
            f"/distribution/jobs/{job_uuid}/deliveries",
            headers=self._headers(self.manager_token),
        )
        self.assertEqual(res_deliv.status_code, 200)
        raw_json_str = res_deliv.text
        records = res_deliv.json()["items"]
        self.assertGreater(len(records), 0)

        for r in records:
            masked = r.get("masked_recipient_address")
            self.assertIsNotNone(masked)
            self.assertIn("***", masked)
            self.assertIn("@example.gov.in", masked)
            # Verify raw recipient_address is omitted from top-level schema
            self.assertNotIn("recipient_address", r)

        # Verify raw PII emails never appear in serialized JSON payload
        self.assertNotIn("aarav@example.gov.in", raw_json_str)
        self.assertNotIn("priya@example.gov.in", raw_json_str)

    def test_raw_recipient_address_strictly_omitted_from_nested_fields_and_all_channels(self):
        """Verify raw recipient addresses are absent from top-level and nested response fields across channels."""
        # Process an SMS job to generate attempts and response metadata
        res_create = self.client.post(
            "/distribution/jobs",
            json={"campaign_id": self.campaign.id, "channel": "SMS"},
            headers=self._headers(self.manager_token),
        )
        job_uuid = res_create.json()["job_id"]

        # Process the job to create delivery attempts with metadata
        res_proc = self.client.post(
            f"/distribution/jobs/{job_uuid}/process",
            headers=self._headers(self.manager_token),
        )
        self.assertEqual(res_proc.status_code, 200)

        # Retrieve deliveries
        res_deliv = self.client.get(
            f"/distribution/jobs/{job_uuid}/deliveries",
            headers=self._headers(self.manager_token),
        )
        self.assertEqual(res_deliv.status_code, 200)
        payload = res_deliv.json()
        raw_text = res_deliv.text

        # Top-level items check
        for rec in payload["items"]:
            # 1. Masked address present
            self.assertIn("masked_recipient_address", rec)
            self.assertTrue(rec["masked_recipient_address"].startswith("+919****"))
            self.assertIn("****", rec["masked_recipient_address"])
            # 2. Raw recipient_address absent
            self.assertNotIn("recipient_address", rec)
            # 3. Check attempts nested array
            for att in rec.get("attempts", []):
                self.assertNotIn("recipient_address", att)
                if "response_metadata" in att and att["response_metadata"]:
                    meta_str = str(att["response_metadata"])
                    self.assertNotIn("+919876543210", meta_str)
                    self.assertNotIn("+919876543211", meta_str)

        # Entire raw JSON payload check: raw phone numbers must not appear anywhere
        self.assertNotIn("+919876543210", raw_text)
        self.assertNotIn("+919876543211", raw_text)

    def test_readiness_invalid_channel_validation(self):
        """Readiness endpoint returns 422 Unprocessable Entity for invalid channel."""
        res = self.client.get(
            f"/distribution/readiness/{self.campaign.id}?channel=CarrierPigeon",
            headers=self._headers(self.comm_token),
        )
        self.assertEqual(res.status_code, 422)
        self.assertIn("Invalid channel", res.json()["detail"])


if __name__ == "__main__":
    unittest.main()

