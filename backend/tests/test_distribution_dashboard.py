"""Integration tests for Task 9 Checkpoint 4: Distribution Dashboard, Metrics, and Concurrency Guards."""

import unittest
import asyncio
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
from app.models.distribution import DistributionJob, DeliveryRecord
from app.core.security import get_password_hash, create_access_token
from sqlalchemy.exc import IntegrityError
from app.models.campaign import Campaign
from app.models.template import Template
from app.models.segment import Segment
from app.services.distribution import (
    create_distribution_job,
    claim_next_queued_job,
    recover_stale_jobs,
    process_job_batch,
    get_distribution_metrics,
)


class TestDistributionDashboard(unittest.TestCase):
    """Test suite for Distribution Dashboard metrics, worker lease concurrency guards, and operational endpoints."""

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
            full_name="Admin Director",
            email="admin@agency.gov.in",
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
        self.comm_user = User(
            full_name="Comm Specialist Sam",
            email="sam@agency.gov.in",
            hashed_password=get_password_hash("CommPass123!"),
            role_id=self.comm_role.id,
            is_active=True,
        )
        self.db.add_all([self.admin_user, self.manager_user, self.comm_user])
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
        self.db.add_all([self.aud1, self.aud2])
        self.db.commit()

        # Tokens
        self.admin_token = create_access_token(self.admin_user.id)
        self.manager_token = create_access_token(self.manager_user.id)
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
        self.db.rollback()
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)
        app.dependency_overrides.clear()

    def test_metrics_distinguishes_completed_vs_completed_with_errors(self):
        """Metrics aggregate must cleanly separate completed jobs from completed_with_errors jobs."""
        job_clean = DistributionJob(
            campaign_id=1,
            channel="Email",
            status="completed",
            total_recipients=5,
            delivered_recipients=5,
            failed_recipients=0,
            skipped_recipients=0,
            created_by=self.manager_user.id,
        )
        job_errors = DistributionJob(
            campaign_id=1,
            channel="SMS",
            status="completed_with_errors",
            total_recipients=5,
            delivered_recipients=3,
            failed_recipients=1,
            skipped_recipients=1,
            created_by=self.manager_user.id,
        )
        self.db.add_all([job_clean, job_errors])
        self.db.commit()

        metrics = get_distribution_metrics(self.db)
        self.assertEqual(metrics["total_jobs"], 2)
        self.assertEqual(metrics["completed_jobs"], 1)
        self.assertEqual(metrics["completed_with_errors_jobs"], 1)

    def test_metrics_active_worker_count_and_stale_jobs(self):
        """Active workers count unexpired leases while stale jobs count expired processing leases."""
        now = datetime.now(timezone.utc)
        job_active_worker = DistributionJob(
            campaign_id=1,
            channel="Email",
            status="processing",
            locked_by="worker-alpha",
            lease_expires_at=now + timedelta(seconds=120),
            total_recipients=10,
            created_by=self.manager_user.id,
        )
        job_stale_worker = DistributionJob(
            campaign_id=1,
            channel="SMS",
            status="processing",
            locked_by="worker-beta",
            lease_expires_at=now - timedelta(seconds=30),  # expired
            total_recipients=10,
            created_by=self.manager_user.id,
        )
        self.db.add_all([job_active_worker, job_stale_worker])
        self.db.commit()

        metrics = get_distribution_metrics(self.db)
        self.assertEqual(metrics["processing_jobs"], 2)
        self.assertEqual(metrics["active_workers_count"], 1)  # only worker-alpha has valid lease
        self.assertEqual(metrics["stale_processing_jobs"], 1) # only worker-beta is expired

    def test_worker_lease_ownership_guard_aborts_on_mismatch(self):
        """If a worker's lease expires and another claims the job, the stale worker must abort execution."""
        job = DistributionJob(
            campaign_id=1,
            channel="Email",
            status="processing",
            locked_by="worker-bravo",  # Currently owned by bravo
            lease_expires_at=datetime.now(timezone.utc) + timedelta(seconds=120),
            total_recipients=1,
            created_by=self.manager_user.id,
        )
        self.db.add(job)
        self.db.commit()

        # Worker alpha attempts to process the batch with its own worker_id
        processed_count, is_complete = asyncio.run(
            process_job_batch(
                db=self.db,
                job_uuid=job.job_id,
                batch_size=10,
                worker_id="worker-alpha",
            )
        )
        # Lease guard triggers, returns 0 and does not modify job
        self.assertEqual(processed_count, 0)
        self.assertFalse(is_complete)
        self.db.refresh(job)
        self.assertEqual(job.locked_by, "worker-bravo")

    def test_metrics_api_endpoint_rbac(self):
        """Admin, Campaign Manager, and Communication Team can view metrics; anonymous cannot."""
        # Unauthenticated request
        resp_anon = self.client.get("/distribution/metrics")
        self.assertEqual(resp_anon.status_code, 401)

        # Communication Team (Read role)
        resp_comm = self.client.get(
            "/distribution/metrics",
            headers={"Authorization": f"Bearer {self.comm_token}"},
        )
        self.assertEqual(resp_comm.status_code, 200)
        data = resp_comm.json()
        self.assertIn("completed_with_errors_jobs", data)
        self.assertIn("active_workers_count", data)
        self.assertIn("stale_processing_jobs", data)

        # Admin
        resp_admin = self.client.get(
            "/distribution/metrics",
            headers={"Authorization": f"Bearer {self.admin_token}"},
        )
        self.assertEqual(resp_admin.status_code, 200)

        # Campaign Manager
        resp_mgr = self.client.get(
            "/distribution/metrics",
            headers={"Authorization": f"Bearer {self.manager_token}"},
        )
        self.assertEqual(resp_mgr.status_code, 200)

    def test_jobs_api_filtering_and_pagination(self):
        """Jobs listing endpoint supports channel, status filtering and pagination."""
        for i in range(5):
            self.db.add(DistributionJob(
                campaign_id=1,
                channel="Email" if i % 2 == 0 else "SMS",
                status="completed" if i < 3 else "queued",
                total_recipients=10,
                created_by=self.manager_user.id,
            ))
        self.db.commit()

        # Filter by channel=SMS
        resp_sms = self.client.get(
            "/distribution/jobs?channel=SMS",
            headers={"Authorization": f"Bearer {self.manager_token}"},
        )
        self.assertEqual(resp_sms.status_code, 200)
        data_sms = resp_sms.json()
        self.assertEqual(data_sms["total"], 2)
        for item in data_sms["items"]:
            self.assertEqual(item["channel"], "SMS")

        # Filter by status=queued
        resp_queued = self.client.get(
            "/distribution/jobs?status=queued",
            headers={"Authorization": f"Bearer {self.manager_token}"},
        )
        self.assertEqual(resp_queued.status_code, 200)
        data_queued = resp_queued.json()
        self.assertEqual(data_queued["total"], 2)

    def test_deliveries_api_masked_addresses_and_filters(self):
        """Deliveries endpoint returns masked recipient addresses and supports status/search filtering."""
        job = DistributionJob(
            campaign_id=1,
            channel="Email",
            status="completed",
            total_recipients=2,
            delivered_recipients=1,
            failed_recipients=1,
            created_by=self.manager_user.id,
        )
        self.db.add(job)
        self.db.commit()

        rec1 = DeliveryRecord(
            job_id=job.id,
            audience_member_id=self.aud1.id,
            channel="Email",
            recipient_address="priya.sharma@example.gov.in",
            delivery_status="delivered",
            rendered_content="Alert content",
            idempotency_key=f"{job.id}:{self.aud1.id}:Email",
        )
        rec2 = DeliveryRecord(
            job_id=job.id,
            audience_member_id=self.aud2.id,
            channel="Email",
            recipient_address="rajesh.kumar@agency.nic.in",
            delivery_status="failed",
            rendered_content="Alert content",
            error_code="PROVIDER_TEMP_FAIL",
            error_message="Simulated temporary SMTP failure",
            idempotency_key=f"{job.id}:{self.aud2.id}:Email",
        )
        self.db.add_all([rec1, rec2])
        self.db.commit()

        # Query deliveries for job
        resp = self.client.get(
            f"/distribution/jobs/{job.job_id}/deliveries",
            headers={"Authorization": f"Bearer {self.manager_token}"},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["total"], 2)
        # Verify masked recipient addresses and ensure raw addresses are never exposed
        for item in data["items"]:
            self.assertIsNotNone(item["masked_recipient_address"])
            self.assertIn("***", item["masked_recipient_address"])
            self.assertNotIn("recipient_address", item)
            # Ensure full address is NOT exposed in masked address field
            self.assertNotIn("priya.sharma@", item["masked_recipient_address"])
            self.assertNotIn("rajesh.kumar@", item["masked_recipient_address"])

        # Ensure raw addresses do not appear anywhere in serialized response payload
        self.assertNotIn("priya.sharma@example.gov.in", resp.text)
        self.assertNotIn("rajesh.kumar@agency.nic.in", resp.text)

        # Filter by delivery status=failed
        resp_failed = self.client.get(
            f"/distribution/jobs/{job.job_id}/deliveries?status=failed",
            headers={"Authorization": f"Bearer {self.manager_token}"},
        )
        self.assertEqual(resp_failed.status_code, 200)
        self.assertEqual(resp_failed.json()["total"], 1)
        self.assertEqual(resp_failed.json()["items"][0]["delivery_status"], "failed")

    def test_empty_metrics_and_graceful_state(self):
        """When no distribution jobs exist, metrics endpoint returns zeroes and null duration gracefully."""
        resp = self.client.get(
            "/distribution/metrics",
            headers={"Authorization": f"Bearer {self.comm_token}"},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["total_jobs"], 0)
        self.assertEqual(data["queued_jobs"], 0)
        self.assertEqual(data["processing_jobs"], 0)
        self.assertEqual(data["completed_jobs"], 0)
        self.assertEqual(data["completed_with_errors_jobs"], 0)
        self.assertEqual(data["failed_jobs"], 0)
        self.assertEqual(data["cancelled_jobs"], 0)
        self.assertEqual(data["active_workers_count"], 0)
        self.assertIsNone(data["avg_processing_duration_seconds"])

    def test_job_cancellation_workflow(self):
        """Queued job can be cancelled by authorized manager, cancelling staged delivery records."""
        job = DistributionJob(
            campaign_id=1,
            channel="Email",
            status="queued",
            total_recipients=1,
            created_by=self.manager_user.id,
        )
        self.db.add(job)
        self.db.commit()

        rec = DeliveryRecord(
            job_id=job.id,
            audience_member_id=self.aud1.id,
            channel="Email",
            recipient_address="aarav@example.gov.in",
            delivery_status="pending",
            rendered_content="Alert content",
            idempotency_key=f"{job.id}:{self.aud1.id}:Email",
        )
        self.db.add(rec)
        self.db.commit()

        resp = self.client.post(
            f"/distribution/jobs/{job.job_id}/cancel",
            headers={"Authorization": f"Bearer {self.manager_token}"},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "cancelled")

        self.db.refresh(rec)
        self.assertEqual(rec.delivery_status, "cancelled")

    def test_idempotency_key_constraint_prevents_duplicate_records(self):
        """Database uniqueness constraint on idempotency_key prevents duplicate delivery staging."""
        job = DistributionJob(
            campaign_id=1,
            channel="Email",
            status="queued",
            total_recipients=1,
            created_by=self.manager_user.id,
        )
        self.db.add(job)
        self.db.commit()

        rec1 = DeliveryRecord(
            job_id=job.id,
            audience_member_id=self.aud1.id,
            channel="Email",
            recipient_address="aarav@example.gov.in",
            rendered_content="Alert content",
            delivery_status="pending",
            idempotency_key=f"{job.id}:{self.aud1.id}:Email",
        )
        self.db.add(rec1)
        self.db.commit()

        # Attempt to insert identical record with duplicate idempotency_key
        rec2 = DeliveryRecord(
            job_id=job.id,
            audience_member_id=self.aud1.id,
            channel="Email",
            recipient_address="aarav@example.gov.in",
            rendered_content="Duplicate attempt",
            delivery_status="pending",
            idempotency_key=f"{job.id}:{self.aud1.id}:Email",
        )
        self.db.add(rec2)
        with self.assertRaises(IntegrityError):
            self.db.commit()
        self.db.rollback()

    def test_duplicate_job_creation_conflict_returns_409(self):
        """Creating an active job when another is already queued or processing returns 409 Conflict."""
        # Seed template & segment
        tmpl = Template(
            title="Fire Alert",
            category="Disaster",
            body="Evacuate {city}.",
            created_by=self.manager_user.id,
        )
        seg = Segment(
            name="Chennai Zone",
            filter_rules={"combinator": "AND", "rules": [{"field": "city", "operator": "equals", "value": "Chennai"}]},
            created_by=self.manager_user.id,
        )
        self.db.add_all([tmpl, seg])
        self.db.commit()

        camp = Campaign(
            name="Fire Evacuation",
            campaign_type="Emergency Alert",
            objective="Evacuate citizens",
            priority="High",
            status="Approved",
            channels=["Email"],
            template_id=tmpl.id,
            created_by=self.manager_user.id,
        )
        camp.segments = [seg]
        self.db.add(camp)
        self.db.commit()

        # First job succeeds
        job1 = create_distribution_job(self.db, camp.id, "Email", self.manager_user)
        self.assertEqual(job1.status, "queued")

        # Second job creation attempt while job1 is still active returns 409 Conflict
        resp = self.client.post(
            "/distribution/jobs",
            json={"campaign_id": camp.id, "channel": "Email"},
            headers={"Authorization": f"Bearer {self.manager_token}"},
        )
        self.assertEqual(resp.status_code, 409)
        self.assertIn("already 'queued'", resp.json()["detail"])

    def test_terminal_job_process_batch_noop(self):
        """Calling process_job_batch on completed or failed jobs returns (0, False) without altering status."""
        job = DistributionJob(
            campaign_id=1,
            channel="Email",
            status="completed",
            total_recipients=1,
            delivered_recipients=1,
            created_by=self.manager_user.id,
        )
        self.db.add(job)
        self.db.commit()

        count, has_more = asyncio.run(
            process_job_batch(self.db, job.job_id, batch_size=10)
        )
        self.assertEqual(count, 0)
        self.assertFalse(has_more)
        self.db.refresh(job)
        self.assertEqual(job.status, "completed")

    def test_avg_processing_duration_calculation(self):
        """Metrics calculates average processing duration across finished jobs accurately."""
        now = datetime.now(timezone.utc)
        job1 = DistributionJob(
            campaign_id=1,
            channel="Email",
            status="completed",
            started_at=now - timedelta(seconds=120),
            completed_at=now - timedelta(seconds=60),  # 60s
            created_by=self.manager_user.id,
        )
        job2 = DistributionJob(
            campaign_id=1,
            channel="SMS",
            status="completed_with_errors",
            started_at=now - timedelta(seconds=200),
            completed_at=now - timedelta(seconds=100),  # 100s
            created_by=self.manager_user.id,
        )
        self.db.add_all([job1, job2])
        self.db.commit()

        metrics = get_distribution_metrics(self.db)
        # Average of 60s and 100s = 80.0s
        self.assertEqual(metrics["avg_processing_duration_seconds"], 80.0)

    def test_concurrent_worker_claim_and_stale_fencing(self):
        """Deterministic simulation of worker claim, lease recovery, and stale worker rejection."""
        job = DistributionJob(
            campaign_id=1,
            channel="Email",
            status="queued",
            total_recipients=1,
            created_by=self.manager_user.id,
        )
        self.db.add(job)
        self.db.commit()

        # 1. Worker 1 claims job
        claimed_w1 = claim_next_queued_job(self.db, worker_id="worker-node-1", lease_seconds=60)
        self.assertIsNotNone(claimed_w1)
        self.assertEqual(claimed_w1.locked_by, "worker-node-1")
        self.assertEqual(claimed_w1.status, "processing")

        # 2. Worker 2 attempts to claim - finds no queued job
        claimed_w2 = claim_next_queued_job(self.db, worker_id="worker-node-2", lease_seconds=60)
        self.assertIsNone(claimed_w2)

        # 3. Simulate Worker 1 crash: lease expires
        claimed_w1.lease_expires_at = datetime.now(timezone.utc) - timedelta(seconds=10)
        self.db.commit()

        # 4. Stale recovery runs
        recovered = recover_stale_jobs(self.db, lease_seconds=60)
        self.assertEqual(len(recovered), 1)
        self.db.refresh(job)
        self.assertEqual(job.status, "queued")
        self.assertIsNone(job.locked_by)

        # 5. Worker 2 now successfully claims the recovered job
        claimed_w2_reclaim = claim_next_queued_job(self.db, worker_id="worker-node-2", lease_seconds=60)
        self.assertIsNotNone(claimed_w2_reclaim)
        self.assertEqual(claimed_w2_reclaim.locked_by, "worker-node-2")

        # 6. Zombie Worker 1 wakes up and attempts to execute batch -> strictly rejected!
        proc_count, is_more = asyncio.run(
            process_job_batch(self.db, job.job_id, batch_size=10, worker_id="worker-node-1")
        )
        self.assertEqual(proc_count, 0)
        self.assertFalse(is_more)
        self.db.refresh(job)
        self.assertEqual(job.locked_by, "worker-node-2")
