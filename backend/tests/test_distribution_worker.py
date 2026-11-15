"""Comprehensive test suite for Task 9 Checkpoint 3: Queue Worker, Processing Reliability, and Delivery Observability."""

import unittest
import asyncio
from datetime import datetime, timezone, timedelta
from sqlalchemy import create_engine, select
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
from app.models.audience import AudienceMember
from app.models.distribution import DistributionJob, DeliveryRecord, DeliveryAttempt
from app.core.security import get_password_hash, create_access_token
from app.workers.worker_config import WorkerConfig, generate_default_worker_id
from app.workers.distribution_worker import DistributionWorker
from app.services.distribution import (
    create_distribution_job,
    claim_next_queued_job,
    recover_stale_jobs,
    update_worker_heartbeat,
    process_job_batch,
    get_distribution_metrics,
)


class TestDistributionWorker(unittest.TestCase):
    """Unit and integration tests for independent database-backed worker, recovery, and observability."""

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

        self.manager_user = User(
            full_name="Manager Maya",
            email="maya@agency.gov.in",
            hashed_password=get_password_hash("ManagerPass123!"),
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
        self.db.add_all([self.manager_user, self.comm_user])
        self.db.commit()

        # Seed template
        self.template = Template(
            title="Vaccination Advisory",
            category="Health",
            body="Dear {name}, polio vaccination camp is active in {city}.",
            created_by=self.manager_user.id,
        )
        self.db.add(self.template)
        self.db.commit()

        # Seed multiple audience members
        self.members = []
        for i in range(5):
            m = AudienceMember(
                name=f"Citizen {i}",
                email=f"citizen{i}@example.gov.in",
                phone=f"+91987654321{i}",
                city="Chennai",
                consent_status=True,
            )
            self.members.append(m)
        self.db.add_all(self.members)
        self.db.commit()

        # Seed segment
        self.segment = Segment(
            name="Chennai All",
            filter_rules={
                "combinator": "AND",
                "rules": [{"field": "city", "operator": "equals", "value": "Chennai"}],
            },
            created_by=self.manager_user.id,
        )
        self.db.add(self.segment)
        self.db.commit()

        # Seed campaign
        self.campaign = Campaign(
            name="Health Mission 2026",
            campaign_type="Health",
            objective="Vaccination Drive",
            priority="High",
            status="Approved",
            channels=["Email", "SMS"],
            template_id=self.template.id,
            created_by=self.manager_user.id,
        )
        self.campaign.segments = [self.segment]
        self.db.add(self.campaign)
        self.db.commit()

        self.manager_token = create_access_token(self.manager_user.id)
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
    # 1. Worker Configuration & Identity
    # -------------------------------------------------------------------------

    def test_worker_config_defaults_and_identity(self):
        """Worker configuration instantiates with safe defaults and traceable worker ID."""
        config = WorkerConfig()
        self.assertIsNotNone(config.worker_id)
        self.assertTrue(config.worker_id.startswith("worker-"))
        self.assertEqual(config.batch_size, 50)
        self.assertEqual(config.lease_duration_seconds, 300)
        self.assertEqual(config.max_recoveries, 3)

        # Custom worker ID
        custom_id = generate_default_worker_id()
        self.assertIn("-", custom_id)

    # -------------------------------------------------------------------------
    # 2. Worker One-Shot Execution & Empty Queue
    # -------------------------------------------------------------------------

    def test_worker_one_shot_empty_queue(self):
        """Worker executing one-shot against empty queue finishes cleanly with 0 jobs claimed."""
        worker = DistributionWorker(WorkerConfig(worker_id="test-worker-1"))
        # Patch SessionLocal to use test SQLite engine
        import app.workers.distribution_worker as dw_mod
        orig_session_local = dw_mod.SessionLocal
        dw_mod.SessionLocal = self.TestingSessionLocal

        try:
            stats = asyncio.run(worker.run_one_shot())
            self.assertEqual(stats["jobs_claimed"], 0)
            self.assertEqual(stats["records_processed"], 0)
            self.assertEqual(stats["stale_jobs_recovered"], 0)
        finally:
            dw_mod.SessionLocal = orig_session_local

    def test_worker_one_shot_processes_queued_job(self):
        """Worker one-shot claims and processes a queued job to completion."""
        # Create a job with 5 recipients
        job = create_distribution_job(self.db, self.campaign.id, "Email", self.manager_user)
        self.assertEqual(job.status, "queued")

        import app.workers.distribution_worker as dw_mod
        orig_session_local = dw_mod.SessionLocal
        dw_mod.SessionLocal = self.TestingSessionLocal

        worker = DistributionWorker(WorkerConfig(worker_id="test-worker-1", batch_size=10))
        try:
            stats = asyncio.run(worker.run_one_shot())
            self.assertEqual(stats["jobs_claimed"], 1)
            self.assertEqual(stats["jobs_completed"], 1)
            self.assertEqual(stats["records_processed"], 5)

            # Check job state in database (expire session cache to reload from DB)
            self.db.expire_all()
            refreshed = self.db.get(DistributionJob, job.id)
            self.assertEqual(refreshed.status, "completed")
            self.assertEqual(refreshed.delivered_recipients, 5)
            self.assertIsNone(refreshed.locked_by)  # Lock cleared after completion
        finally:
            dw_mod.SessionLocal = orig_session_local

    # -------------------------------------------------------------------------
    # 3. Bounded Batch Processing
    # -------------------------------------------------------------------------

    def test_bounded_batch_processing_splits_across_batches(self):
        """Large jobs are processed in bounded batches without unbounded memory loads."""
        job = create_distribution_job(self.db, self.campaign.id, "Email", self.manager_user)
        self.assertEqual(job.status, "queued")

        # Process in batches of 2 (5 recipients total -> 2, 2, 1 = 3 batches)
        # Batch 1
        processed_1, has_more_1 = asyncio.run(
            process_job_batch(self.db, job.job_id, batch_size=2, worker_id="batch-worker")
        )
        self.assertEqual(processed_1, 2)
        self.assertTrue(has_more_1)

        # Batch 2
        processed_2, has_more_2 = asyncio.run(
            process_job_batch(self.db, job.job_id, batch_size=2, worker_id="batch-worker")
        )
        self.assertEqual(processed_2, 2)
        self.assertTrue(has_more_2)

        # Batch 3 (final)
        processed_3, has_more_3 = asyncio.run(
            process_job_batch(self.db, job.job_id, batch_size=2, worker_id="batch-worker")
        )
        self.assertEqual(processed_3, 1)
        self.assertFalse(has_more_3)

        # Final check
        refreshed = self.db.get(DistributionJob, job.id)
        self.assertEqual(refreshed.status, "completed")
        self.assertEqual(refreshed.delivered_recipients, 5)

    # -------------------------------------------------------------------------
    # 4. Atomic Job Claiming & Concurrency Safeguards
    # -------------------------------------------------------------------------

    def test_atomic_job_claiming_prevents_duplicate_claims(self):
        """When Worker 1 claims a job, Worker 2 cannot claim the same job simultaneously."""
        job = create_distribution_job(self.db, self.campaign.id, "Email", self.manager_user)
        self.assertEqual(job.status, "queued")

        # Worker 1 claims the job
        claimed_job_1 = claim_next_queued_job(self.db, worker_id="worker-alpha", lease_seconds=120)
        self.assertIsNotNone(claimed_job_1)
        self.assertEqual(claimed_job_1.id, job.id)
        self.assertEqual(claimed_job_1.status, "processing")
        self.assertEqual(claimed_job_1.locked_by, "worker-alpha")

        # Worker 2 attempts to claim next queued job -> None available!
        claimed_job_2 = claim_next_queued_job(self.db, worker_id="worker-beta", lease_seconds=120)
        self.assertIsNone(claimed_job_2)

    def test_completed_or_cancelled_job_cannot_be_claimed(self):
        """Cancelled or completed jobs are never claimed by workers."""
        job = create_distribution_job(self.db, self.campaign.id, "Email", self.manager_user)
        job.status = "cancelled"
        self.db.commit()

        claimed = claim_next_queued_job(self.db, worker_id="worker-gamma")
        self.assertIsNone(claimed)

    # -------------------------------------------------------------------------
    # 5. Worker Leases, Stale Processing Recovery & Max Recoveries
    # -------------------------------------------------------------------------

    def test_stale_job_recovery_when_lease_expired(self):
        """A job stuck in processing whose lease expired is recovered to queued status."""
        job = create_distribution_job(self.db, self.campaign.id, "Email", self.manager_user)
        job.status = "processing"
        job.locked_by = "crashed-worker-99"
        job.locked_at = datetime.now(timezone.utc) - timedelta(seconds=400)
        job.lease_expires_at = datetime.now(timezone.utc) - timedelta(seconds=100)  # Expired!

        # Put one record in 'processing' state as if the worker crashed mid-dispatch
        first_rec = self.db.execute(
            select(DeliveryRecord).where(DeliveryRecord.job_id == job.id)
        ).scalars().first()
        first_rec.delivery_status = "processing"
        self.db.commit()

        # Run recovery
        recovered = recover_stale_jobs(self.db, lease_seconds=300, max_recoveries=3)
        self.assertEqual(len(recovered), 1)
        self.assertEqual(recovered[0].id, job.id)

        # Check job is now back in queued state with incremented recovery count
        self.db.refresh(job)
        self.assertEqual(job.status, "queued")
        self.assertEqual(job.recovery_count, 1)
        self.assertIsNone(job.locked_by)
        self.assertIsNone(job.lease_expires_at)

        # Check orphaned record was safely reset to pending
        self.db.refresh(first_rec)
        self.assertEqual(first_rec.delivery_status, "pending")

    def test_active_lease_not_recovered(self):
        """Jobs with active, unexpired leases are not reclaimed by stale job recovery."""
        job = create_distribution_job(self.db, self.campaign.id, "Email", self.manager_user)
        job.status = "processing"
        job.locked_by = "active-worker-1"
        job.lease_expires_at = datetime.now(timezone.utc) + timedelta(seconds=200)  # Still active!
        self.db.commit()

        recovered = recover_stale_jobs(self.db, lease_seconds=300, max_recoveries=3)
        self.assertEqual(len(recovered), 0)

        self.db.refresh(job)
        self.assertEqual(job.status, "processing")
        self.assertEqual(job.locked_by, "active-worker-1")

    def test_stale_job_exceeding_max_recoveries_marked_failed(self):
        """Job that exceeds max_recoveries is permanently marked FAILED to prevent infinite loops."""
        job = create_distribution_job(self.db, self.campaign.id, "Email", self.manager_user)
        job.status = "processing"
        job.recovery_count = 3  # Already reached max!
        job.lease_expires_at = datetime.now(timezone.utc) - timedelta(seconds=50)
        self.db.commit()

        recovered = recover_stale_jobs(self.db, lease_seconds=300, max_recoveries=3)
        self.assertEqual(len(recovered), 1)

        self.db.refresh(job)
        self.assertEqual(job.status, "failed")
        self.assertIn("exceeded", job.error_summary.lower())

    def test_worker_heartbeat_updates_lease(self):
        """Worker heartbeat refreshes lease expiration timestamp."""
        job = create_distribution_job(self.db, self.campaign.id, "Email", self.manager_user)
        job.status = "processing"
        job.locked_by = "worker-heartbeat"
        initial_expiry = datetime.now(timezone.utc) + timedelta(seconds=100)
        job.lease_expires_at = initial_expiry
        self.db.commit()

        success = update_worker_heartbeat(self.db, job.id, "worker-heartbeat", lease_seconds=400)
        self.assertTrue(success)

        self.db.refresh(job)
        actual_expiry = job.lease_expires_at if job.lease_expires_at.tzinfo else job.lease_expires_at.replace(tzinfo=timezone.utc)
        self.assertGreater(actual_expiry, initial_expiry)

    # -------------------------------------------------------------------------
    # 6. Retry Scheduling & Bounded Exponential Backoff
    # -------------------------------------------------------------------------

    def test_exponential_backoff_retry_scheduling(self):
        """Retryable failure computes exponential backoff next_retry_at and excludes premature processing."""
        # Create audience member with simulation address triggering temporary failure
        temp_fail_member = AudienceMember(
            name="Retry Citizen",
            email="fail_temp@example.gov.in",
            phone="+919876543290",
            city="Chennai",
            consent_status=True,
        )
        self.db.add(temp_fail_member)
        self.db.commit()

        job = create_distribution_job(self.db, self.campaign.id, "Email", self.manager_user)

        # Process batch
        asyncio.run(process_job_batch(self.db, job.job_id, batch_size=10, base_backoff_seconds=60))

        # Check failing record
        fail_rec = self.db.execute(
            select(DeliveryRecord).where(
                DeliveryRecord.job_id == job.id,
                DeliveryRecord.recipient_address == "fail_temp@example.gov.in",
            )
        ).scalar_one()

        self.assertEqual(fail_rec.delivery_status, "retrying")
        self.assertEqual(fail_rec.attempt_count, 1)
        self.assertIsNotNone(fail_rec.next_retry_at)
        # Should be scheduled in the future (~60s from now)
        actual_next_retry = fail_rec.next_retry_at if fail_rec.next_retry_at.tzinfo else fail_rec.next_retry_at.replace(tzinfo=timezone.utc)
        self.assertGreater(actual_next_retry, datetime.now(timezone.utc))

        # Attempt to process batch again immediately -> failing record skipped because next_retry_at > now
        processed_again, _ = asyncio.run(
            process_job_batch(self.db, job.job_id, batch_size=10)
        )
        self.assertEqual(processed_again, 0)
        self.assertEqual(fail_rec.attempt_count, 1)  # Not incremented prematurely!

    # -------------------------------------------------------------------------
    # 7. Operational Observability & Metrics Endpoint
    # -------------------------------------------------------------------------

    def test_metrics_endpoint_aggregates(self):
        """GET /distribution/metrics returns accurate aggregate queue metrics."""
        # Create a job and process it
        job = create_distribution_job(self.db, self.campaign.id, "Email", self.manager_user)
        asyncio.run(process_job_batch(self.db, job.job_id, batch_size=10))

        res = self.client.get("/distribution/metrics", headers=self._headers(self.comm_token))
        self.assertEqual(res.status_code, 200)
        data = res.json()

        self.assertIn("total_jobs", data)
        self.assertIn("queued_jobs", data)
        self.assertIn("completed_jobs", data)
        self.assertIn("total_delivery_records", data)
        self.assertIn("delivered_deliveries", data)
        self.assertIn("stale_processing_jobs", data)

        self.assertGreaterEqual(data["total_jobs"], 1)
        self.assertGreaterEqual(data["delivered_deliveries"], 5)
        # Ensure recipient personal info is NOT present in metrics
        for key in data:
            self.assertNotIn("@", str(data[key]))
            self.assertNotIn("+91", str(data[key]))

    def test_metrics_endpoint_rbac(self):
        """Unauthenticated requests to /distribution/metrics return 401."""
        res = self.client.get("/distribution/metrics")
        self.assertEqual(res.status_code, 401)


class TestPostgreSQLWorkerConcurrency(unittest.TestCase):
    """
    Dedicated concurrency integration test suite running specifically against
    the PostgreSQL development database (masscommai_dev).
    Demonstrates competing worker processes using SELECT ... FOR UPDATE SKIP LOCKED
    row-level locking, ensuring that:
    1. Competing workers never lock or process the same queued job.
    2. A row locked by Worker 1 in an active transaction is cleanly skipped by Worker 2.
    3. Complete state restoration guarantees zero leftover test data in masscommai_dev.
    """

    @classmethod
    def setUpClass(cls):
        try:
            import psycopg
            conn = psycopg.connect("postgresql://hariprasathc@localhost:5432/masscommai_dev")
            conn.close()
        except Exception as exc:
            raise unittest.SkipTest(f"PostgreSQL masscommai_dev not reachable: {exc}")

        cls.pg_engine = create_engine(
            "postgresql+psycopg://hariprasathc@localhost:5432/masscommai_dev",
            pool_pre_ping=True,
        )
        cls.PgSession = sessionmaker(bind=cls.pg_engine, autocommit=False, autoflush=False)

    def setUp(self):
        self.session = self.PgSession()
        # Find first existing user in masscommai_dev
        user = self.session.execute(select(User).limit(1)).scalar_one_or_none()
        if not user:
            self.session.close()
            raise unittest.SkipTest("No user found in PostgreSQL dev database")
        self.user_id = user.id

        # Clean up any residual test campaigns from aborted runs
        from sqlalchemy import delete
        residual_camps = self.session.execute(
            select(Campaign.id).where(Campaign.name == "PG Concurrency Test Campaign")
        ).scalars().all()
        if residual_camps:
            self.session.execute(delete(DeliveryRecord).where(
                DeliveryRecord.job_id.in_(select(DistributionJob.id).where(DistributionJob.campaign_id.in_(residual_camps)))
            ))
            self.session.execute(delete(DistributionJob).where(DistributionJob.campaign_id.in_(residual_camps)))
            self.session.execute(delete(Campaign).where(Campaign.id.in_(residual_camps)))
            self.session.commit()

        # Create temporary campaign for isolation
        self.campaign = Campaign(
            name="PG Concurrency Test Campaign",
            campaign_type="Emergency Alert",
            objective="Concurrency Lock Verification",
            priority="High",
            status="Approved",
            channels=["Email"],
            created_by=self.user_id,
        )
        self.session.add(self.campaign)
        self.session.commit()
        self.session.refresh(self.campaign)
        self.created_job_ids = []
        self.created_aud_ids = []

    def tearDown(self):
        # Clean up any jobs and campaigns created during this test
        try:
            from sqlalchemy import delete
            if self.created_job_ids:
                self.session.execute(delete(DeliveryRecord).where(DeliveryRecord.job_id.in_(self.created_job_ids)))
                self.session.execute(delete(DistributionJob).where(DistributionJob.id.in_(self.created_job_ids)))
            if self.created_aud_ids:
                self.session.execute(delete(AudienceMember).where(AudienceMember.id.in_(self.created_aud_ids)))
            if hasattr(self, "campaign") and self.campaign:
                self.session.execute(delete(Campaign).where(Campaign.id == self.campaign.id))
            self.session.commit()
        except Exception:
            self.session.rollback()
        finally:
            self.session.close()

    def test_competing_workers_skip_locked_row_locks(self):
        """Two competing workers concurrently query queued jobs with FOR UPDATE SKIP LOCKED on PostgreSQL."""
        # Create two queued jobs
        job_a = DistributionJob(
            campaign_id=self.campaign.id,
            channel="Email",
            status="queued",
            total_recipients=1,
            eligible_recipients=1,
            queued_recipients=1,
            created_by=self.user_id,
        )
        job_b = DistributionJob(
            campaign_id=self.campaign.id,
            channel="Email",
            status="queued",
            total_recipients=1,
            eligible_recipients=1,
            queued_recipients=1,
            created_by=self.user_id,
        )
        self.session.add_all([job_a, job_b])
        self.session.commit()
        self.created_job_ids = [job_a.id, job_b.id]

        # Open two distinct database connections/sessions
        session_worker_1 = self.PgSession()
        session_worker_2 = self.PgSession()

        try:
            # Worker 1 queries with SKIP LOCKED (in open transaction holding row lock)
            stmt1 = (
                select(DistributionJob)
                .where(
                    DistributionJob.status == "queued",
                    DistributionJob.id.in_(self.created_job_ids),
                )
                .order_by(DistributionJob.id.asc())
                .limit(1)
                .with_for_update(skip_locked=True)
            )
            locked_job_1 = session_worker_1.execute(stmt1).scalar_one_or_none()
            self.assertIsNotNone(locked_job_1)
            self.assertEqual(locked_job_1.id, job_a.id)

            # While Worker 1 holds the lock on job_a, Worker 2 executes the SAME query
            # Because job_a is locked, SKIP LOCKED skips job_a and acquires job_b!
            stmt2 = (
                select(DistributionJob)
                .where(
                    DistributionJob.status == "queued",
                    DistributionJob.id.in_(self.created_job_ids),
                )
                .order_by(DistributionJob.id.asc())
                .limit(1)
                .with_for_update(skip_locked=True)
            )
            locked_job_2 = session_worker_2.execute(stmt2).scalar_one_or_none()
            self.assertIsNotNone(locked_job_2)
            self.assertEqual(locked_job_2.id, job_b.id)

            # Verify Worker 1 and Worker 2 got completely different jobs
            self.assertNotEqual(locked_job_1.id, locked_job_2.id)

            # If Worker 3 queries now, both jobs are locked, so it gets None
            session_worker_3 = self.PgSession()
            try:
                locked_job_3 = session_worker_3.execute(stmt1).scalar_one_or_none()
                self.assertIsNone(locked_job_3)
            finally:
                session_worker_3.rollback()
                session_worker_3.close()

        finally:
            session_worker_1.rollback()
            session_worker_1.close()
            session_worker_2.rollback()
            session_worker_2.close()

    def test_stale_worker_atomic_fencing_prevents_stale_commit_on_postgres(self):
        """
        Tests the exact race condition on live PostgreSQL:
        1. Worker A claims a job.
        2. Worker A's lease expires.
        3. Worker B recovers the expired job and acquires a new lease.
        4. Worker A attempts to commit stale job and delivery updates.
        5. Atomic SELECT ... FOR UPDATE fencing blocks Worker A and preserves Worker B's state.
        """
        # Create a queued job with a delivery record
        job = DistributionJob(
            campaign_id=self.campaign.id,
            channel="Email",
            status="queued",
            total_recipients=1,
            eligible_recipients=1,
            queued_recipients=1,
            created_by=self.user_id,
        )
        self.session.add(job)
        self.session.commit()
        self.created_job_ids = [job.id]

        # Query or create an audience member
        aud = self.session.execute(select(AudienceMember).limit(1)).scalar_one_or_none()
        if not aud:
            aud = AudienceMember(
                name="Postgres Audit Recipient",
                email="pg.audit@example.gov.in",
                phone="+919876543299",
                city="Chennai",
                consent_status=True,
            )
            self.session.add(aud)
            self.session.commit()
            self.session.refresh(aud)
            self.created_aud_ids.append(aud.id)

        record = DeliveryRecord(
            job_id=job.id,
            audience_member_id=aud.id,
            channel="Email",
            recipient_address=aud.email,
            delivery_status="pending",
            rendered_content="Test PostgreSQL content",
            idempotency_key=f"{job.id}:{aud.id}:Email",
        )
        self.session.add(record)
        self.session.commit()

        session_worker_a = self.PgSession()
        session_worker_b = self.PgSession()

        try:
            # 1. Worker A claims the job
            claimed_a = claim_next_queued_job(session_worker_a, worker_id="worker-A-pg", lease_seconds=5)
            self.assertIsNotNone(claimed_a)
            self.assertEqual(claimed_a.locked_by, "worker-A-pg")
            gen_a = claimed_a.recovery_count

            # 2. Worker A's lease expires in the past
            claimed_a.lease_expires_at = datetime.now(timezone.utc) - timedelta(seconds=60)
            session_worker_a.commit()

            # 3. Worker B recovers the stale job and claims it
            recovered_jobs = recover_stale_jobs(session_worker_b, lease_seconds=10)
            self.assertEqual(len(recovered_jobs), 1)
            self.assertEqual(recovered_jobs[0].id, job.id)
            self.assertEqual(recovered_jobs[0].recovery_count, 1)

            claimed_b = claim_next_queued_job(session_worker_b, worker_id="worker-B-pg", lease_seconds=120)
            self.assertIsNotNone(claimed_b)
            self.assertEqual(claimed_b.locked_by, "worker-B-pg")
            self.assertEqual(claimed_b.recovery_count, 1)

            # 4. Worker A attempts to process and commit updates using its stale lease
            processed, has_more = asyncio.run(
                process_job_batch(
                    db=session_worker_a,
                    job_uuid=job.job_id,
                    batch_size=10,
                    worker_id="worker-A-pg",
                    expected_recovery_count=gen_a,
                )
            )

            # 5. Verify atomic fencing stopped Worker A completely
            self.assertEqual(processed, 0)
            self.assertFalse(has_more)

            # 6. Verify Worker B's ownership and state on PostgreSQL remain pristine
            session_verify = self.PgSession()
            try:
                db_job = session_verify.get(DistributionJob, job.id)
                self.assertEqual(db_job.locked_by, "worker-B-pg")
                self.assertEqual(db_job.recovery_count, 1)
                self.assertEqual(db_job.status, "processing")
                self.assertEqual(db_job.delivered_recipients, 0)
            finally:
                session_verify.close()

        finally:
            session_worker_a.rollback()
            session_worker_a.close()
            session_worker_b.rollback()
            session_worker_b.close()


if __name__ == "__main__":
    unittest.main()

