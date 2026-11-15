"""
Test Suite: Approval Workflow & Distribution Security Remediation (Phase 1A)
Enforces:
1. Mandatory Quality Assessment before Content Approval (Invariants A, B, C, D).
2. Strict Distribution Pre-Flight Eligibility (Invariant E).
3. Hard guarantee that mocked delivery provider is NEVER invoked for ineligible content.
"""

import asyncio
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.main import app
from app.core.security import create_access_token, get_password_hash
from app.models.user import User, Role
from app.models.content_asset import ContentAsset
from app.models.campaign import Campaign
from app.models.template import Template
from app.models.audience import AudienceMember
from app.models.segment import Segment
from app.models.distribution import DistributionJob, DeliveryRecord, DeliveryAttempt
from app.services.distribution.base import JobStatus, DeliveryStatus
from app.models.content_quality import ContentQualityAssessment, ContentQualityFinding
from app.models.compliance_rule import ComplianceRule
from app.schemas.content_asset import ContentReviewStatusUpdate
from app.services.content_service import update_review_status
from app.services.quality_service import (
    evaluate_content_asset,
    get_editorial_readiness,
    validate_content_approval_readiness,
    validate_content_dispatch_eligibility,
    compute_content_version_hash,
)
from app.services.distribution.job_service import check_campaign_readiness, create_distribution_job
from app.services.distribution.delivery_service import process_job_batch
from app.services.distribution.providers import BaseDeliveryProvider


class TestApprovalWorkflowSecurityRemediation:
    """Comprehensive test suite for Phase 1A Approval and Distribution Security Invariants."""

    @pytest.fixture(autouse=True)
    def setup_database(self):
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        Base.metadata.create_all(bind=self.engine)
        self.db: Session = TestingSessionLocal()

        # Seed Roles
        admin_role = Role(name="Admin", description="System Administrator")
        manager_role = Role(name="Campaign Manager", description="Campaign Manager")
        author_role = Role(name="Communication Team", description="Author")
        self.db.add_all([admin_role, manager_role, author_role])
        self.db.commit()

        # Seed Users
        self.admin_user = User(
            email="admin@gov.in",
            hashed_password=get_password_hash("AdminPass123!"),
            full_name="Admin Officer",
            role_id=admin_role.id,
            is_active=True,
        )
        self.manager_user = User(
            email="manager@gov.in",
            hashed_password=get_password_hash("ManagerPass123!"),
            full_name="Campaign Manager",
            role_id=manager_role.id,
            is_active=True,
        )
        self.author_user = User(
            email="author@gov.in",
            hashed_password=get_password_hash("AuthorPass123!"),
            full_name="Author Officer",
            role_id=author_role.id,
            is_active=True,
        )
        self.db.add_all([self.admin_user, self.manager_user, self.author_user])
        self.db.commit()

        # Setup TestClient with DB override
        def override_get_db():
            try:
                yield self.db
            finally:
                pass

        from app.db.session import get_db
        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)

        self.admin_token = create_access_token(self.admin_user.id)
        self.manager_token = create_access_token(self.manager_user.id)
        self.author_token = create_access_token(self.author_user.id)

        yield

        app.dependency_overrides.clear()
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)

    def _headers(self, token: str) -> dict:
        return {"Authorization": f"Bearer {token}"}

    def _create_sample_asset(self, review_status: str = "Draft", body: str = "Urgent Flood Advisory: Stay indoors.") -> ContentAsset:
        asset = ContentAsset(
            title="Monsoon Advisory",
            body=body,
            category="Disaster Preparedness",
            tone="urgent",
            channel="SMS",
            source_language="en",
            review_status=review_status,
            created_by=self.author_user.id,
        )
        self.db.add(asset)
        self.db.commit()
        self.db.refresh(asset)
        return asset

    def _create_clean_assessment(self, asset: ContentAsset, status: str = "completed") -> ContentQualityAssessment:
        version_hash = compute_content_version_hash(asset.title, asset.body, asset.call_to_action)
        assessment = ContentQualityAssessment(
            content_asset_id=asset.id,
            content_version_hash=version_hash,
            overall_score=95.0,
            status=status,
            dimension_scores={"readability": 90, "clarity": 95, "channel": 100},
            evaluator_type="deterministic",
            critical_issues_count=0,
            created_by=self.manager_user.id,
        )
        self.db.add(assessment)
        self.db.commit()
        self.db.refresh(assessment)
        return assessment

    def _create_critical_assessment(self, asset: ContentAsset) -> ContentQualityAssessment:
        version_hash = compute_content_version_hash(asset.title, asset.body, asset.call_to_action)
        assessment = ContentQualityAssessment(
            content_asset_id=asset.id,
            content_version_hash=version_hash,
            overall_score=40.0,
            status="completed_with_warnings",
            dimension_scores={"readability": 40, "channel": 40},
            evaluator_type="deterministic",
            critical_issues_count=1,
            created_by=self.manager_user.id,
        )
        self.db.add(assessment)
        self.db.flush()

        finding = ContentQualityFinding(
            assessment_id=assessment.id,
            category="placeholder",
            severity="critical",
            title="Unclosed placeholder brace",
            explanation="Token {name is malformed",
            affected_text="{name",
            reviewer_decision="pending",
        )
        self.db.add(finding)
        self.db.commit()
        self.db.refresh(assessment)
        return assessment

    # =========================================================================
    # PART 1: APPROVAL INVARIANT TESTS (Invariants A, B, C, D)
    # =========================================================================

    def test_approval_blocked_when_no_assessment_exists(self):
        """Invariant A: Content cannot be approved if no quality assessment exists."""
        asset = self._create_sample_asset(review_status="In Review")

        # Attempt approval via service layer
        payload = ContentReviewStatusUpdate(review_status="Approved", review_notes="LGTM")
        with pytest.raises(HTTPException) as exc_info:
            update_review_status(self.db, asset.id, payload, self.admin_user)

        assert exc_info.value.status_code == 400
        assert "not been evaluated" in exc_info.value.detail.lower()

        # Attempt approval via API endpoint
        res = self.client.patch(
            f"/content/{asset.id}/review",
            json={"review_status": "Approved", "review_notes": "Attempting bypass"},
            headers=self._headers(self.admin_token),
        )
        assert res.status_code == 400
        assert "not been evaluated" in res.json()["detail"].lower()

        # Verify DB review_status remains unchanged
        self.db.refresh(asset)
        assert asset.review_status == "In Review"
        assert asset.reviewed_by is None

    def test_approval_fails_closed_on_assessment_lookup_failure(self):
        """Invariant A: Assessment verification fails closed if DB lookup raises unexpected error."""
        asset = self._create_sample_asset(review_status="In Review")
        self._create_clean_assessment(asset)

        with patch("app.services.quality_service.get_editorial_readiness", side_effect=RuntimeError("DB query timeout")):
            payload = ContentReviewStatusUpdate(review_status="Approved", review_notes="Approve")
            with pytest.raises(HTTPException) as exc_info:
                update_review_status(self.db, asset.id, payload, self.admin_user)

            assert exc_info.value.status_code == 400
            assert "verification failed" in exc_info.value.detail.lower()

    def test_approval_blocked_when_assessment_belongs_to_different_content(self):
        """Invariant B: Assessment record for another asset cannot authorize approval."""
        asset1 = self._create_sample_asset(review_status="In Review", body="Asset 1 body")
        asset2 = self._create_sample_asset(review_status="In Review", body="Asset 2 body")
        self._create_clean_assessment(asset2)

        # Asset 1 has no assessment of its own
        payload = ContentReviewStatusUpdate(review_status="Approved", review_notes="Approve")
        with pytest.raises(HTTPException) as exc_info:
            update_review_status(self.db, asset1.id, payload, self.admin_user)

        assert exc_info.value.status_code == 400
        assert "not been evaluated" in exc_info.value.detail.lower()

    def test_approval_blocked_when_assessment_status_is_failed(self):
        """Invariant B: Incomplete or failed quality assessments cannot authorize approval."""
        asset = self._create_sample_asset(review_status="In Review")
        self._create_clean_assessment(asset, status="failed")

        payload = ContentReviewStatusUpdate(review_status="Approved", review_notes="Approve")
        with pytest.raises(HTTPException) as exc_info:
            update_review_status(self.db, asset.id, payload, self.admin_user)

        assert exc_info.value.status_code == 400
        assert "failed or was incomplete" in exc_info.value.detail.lower()

    def test_approval_blocked_when_assessment_contains_unresolved_critical_issues(self):
        """Invariant B: Critical compliance or quality findings block approval until resolved."""
        asset = self._create_sample_asset(review_status="In Review")
        self._create_critical_assessment(asset)

        payload = ContentReviewStatusUpdate(review_status="Approved", review_notes="Bypass critical")
        with pytest.raises(HTTPException) as exc_info:
            update_review_status(self.db, asset.id, payload, self.admin_user)

        assert exc_info.value.status_code == 400
        assert "critical issue" in exc_info.value.detail.lower()

    def test_approval_blocked_when_content_modified_after_assessment(self):
        """Invariant C: Stale assessment cannot authorize approval after post-audit edits."""
        asset = self._create_sample_asset(review_status="In Review", body="Original body before edit.")
        self._create_clean_assessment(asset)

        # Modify content without re-evaluation
        asset.body = "Completely altered body with unverified statistics."
        self.db.commit()

        payload = ContentReviewStatusUpdate(review_status="Approved", review_notes="Approve stale")
        with pytest.raises(HTTPException) as exc_info:
            update_review_status(self.db, asset.id, payload, self.admin_user)

        assert exc_info.value.status_code == 400
        assert "modified since the last quality assessment" in exc_info.value.detail.lower()

    def test_approval_allowed_for_valid_current_assessment_by_authorized_user(self):
        """Invariants A, B, C, D: Authorized manager can approve content with valid, current assessment."""
        asset = self._create_sample_asset(review_status="In Review")
        self._create_clean_assessment(asset)

        payload = ContentReviewStatusUpdate(review_status="Approved", review_notes="Editorial sign-off confirmed")
        approved_asset = update_review_status(self.db, asset.id, payload, self.manager_user)

        assert approved_asset.review_status == "Approved"
        assert approved_asset.reviewed_by == self.manager_user.id
        assert approved_asset.reviewed_at is not None
        assert approved_asset.review_notes == "Editorial sign-off confirmed"

    def test_unauthorized_user_cannot_approve_content(self):
        """Invariant D: Author role (non-manager/non-admin) is forbidden from approving content."""
        asset = self._create_sample_asset(review_status="In Review")
        self._create_clean_assessment(asset)

        res = self.client.patch(
            f"/content/{asset.id}/review",
            json={"review_status": "Approved", "review_notes": "Author self-approval attempt"},
            headers=self._headers(self.author_token),
        )
        assert res.status_code == 403
        assert "permission" in res.json()["detail"].lower()

    def test_rejected_content_cannot_transition_directly_to_approved(self):
        """Invariant D: Rejected content must follow existing state machine transitions."""
        asset = self._create_sample_asset(review_status="Rejected")
        asset.review_notes = "Grammar issues found"
        self._create_clean_assessment(asset)

        payload = ContentReviewStatusUpdate(review_status="Approved", review_notes="Skip resubmission")
        with pytest.raises(HTTPException) as exc_info:
            update_review_status(self.db, asset.id, payload, self.admin_user)

        assert exc_info.value.status_code == 400
        assert "cannot transition" in exc_info.value.detail.lower()

    # =========================================================================
    # PART 2: DISTRIBUTION ELIGIBILITY & DISPATCH TESTS (Invariant E)
    # =========================================================================

    def _setup_distribution_campaign(self, root_asset: ContentAsset) -> Campaign:
        # Create Audience Member with affirmative consent
        aud = AudienceMember(
            name="Suresh Raina",
            email="suresh@gov.in",
            phone="+919876543210",
            city="Chennai",
            preferred_language="en",
            consent_status=True,
        )
        self.db.add(aud)
        self.db.commit()

        # Create Segment
        seg = Segment(
            name="All Citizens",
            filter_rules={"combinator": "AND", "rules": [{"field": "city", "operator": "equals", "value": "Chennai"}]},
            created_by=self.manager_user.id,
        )
        self.db.add(seg)
        self.db.commit()

        # Create Campaign
        camp = Campaign(
            name="Disaster Evacuation Alert",
            campaign_type="Emergency Alert",
            priority="High",
            status="Approved",
            channels=["SMS"],
            created_by=self.manager_user.id,
        )
        camp.segments = [seg]
        root_asset.campaign_id = camp.id
        camp.content_assets = [root_asset]
        self.db.add(camp)
        self.db.commit()
        self.db.refresh(camp)
        return camp

    def test_distribution_job_rejected_when_content_is_unapproved(self):
        """Invariant E: Unapproved (Draft) content is blocked from entering distribution."""
        asset = self._create_sample_asset(review_status="Draft")
        self._create_clean_assessment(asset)
        camp = self._setup_distribution_campaign(asset)

        # Readiness check should block
        readiness = check_campaign_readiness(self.db, camp.id, "SMS")
        assert not readiness.is_ready
        assert any("only 'approved' content can be broadcast" in r.lower() for r in readiness.blocking_reasons)

        # Job creation should fail with 400
        with pytest.raises(HTTPException) as exc_info:
            create_distribution_job(self.db, camp.id, "SMS", self.manager_user)
        assert exc_info.value.status_code == 400

    def test_distribution_job_rejected_when_content_has_no_assessment(self):
        """Invariant E: Content with no quality assessment cannot enter distribution."""
        asset = self._create_sample_asset(review_status="Approved")
        # Deliberately omit assessment
        camp = self._setup_distribution_campaign(asset)

        readiness = check_campaign_readiness(self.db, camp.id, "SMS")
        assert not readiness.is_ready
        assert any("no quality assessment" in r.lower() for r in readiness.blocking_reasons)

        with pytest.raises(HTTPException) as exc_info:
            create_distribution_job(self.db, camp.id, "SMS", self.manager_user)
        assert exc_info.value.status_code == 400
        assert "no quality assessment" in exc_info.value.detail.lower()

    def test_distribution_job_rejected_when_content_has_critical_findings(self):
        """Invariant E: Content with unresolved critical issues is blocked from distribution."""
        asset = self._create_sample_asset(review_status="Approved")
        self._create_critical_assessment(asset)
        camp = self._setup_distribution_campaign(asset)

        readiness = check_campaign_readiness(self.db, camp.id, "SMS")
        assert not readiness.is_ready
        assert any("critical compliance findings" in r.lower() for r in readiness.blocking_reasons)

        with pytest.raises(HTTPException) as exc_info:
            create_distribution_job(self.db, camp.id, "SMS", self.manager_user)
        assert exc_info.value.status_code == 400

    def test_distribution_job_succeeds_for_approved_content_with_valid_assessment(self):
        """Invariant E: Approved content with valid, current assessment successfully stages for distribution."""
        asset = self._create_sample_asset(review_status="Approved")
        self._create_clean_assessment(asset)
        camp = self._setup_distribution_campaign(asset)

        readiness = check_campaign_readiness(self.db, camp.id, "SMS")
        assert readiness.is_ready
        assert len(readiness.blocking_reasons) == 0

        job = create_distribution_job(self.db, camp.id, "SMS", self.manager_user)
        assert job.status == JobStatus.QUEUED.value
        assert job.total_recipients == 1
        assert job.eligible_recipients == 1

        records = self.db.query(DeliveryRecord).filter(DeliveryRecord.job_id == job.id).all()
        assert len(records) == 1
        assert records[0].delivery_status == DeliveryStatus.PENDING.value

    @pytest.mark.asyncio
    async def test_worker_preflight_blocks_dispatch_when_approval_revoked_before_execution(self):
        """Invariant E: Worker pre-flight blocks dispatch if approval was revoked after job staging."""
        asset = self._create_sample_asset(review_status="Approved")
        self._create_clean_assessment(asset)
        camp = self._setup_distribution_campaign(asset)

        # Stage distribution job
        job = create_distribution_job(self.db, camp.id, "SMS", self.manager_user)

        # Revoke approval before worker execution
        asset.review_status = "In Review"
        self.db.commit()

        # Mock delivery provider to track invocations
        mock_provider = MagicMock(spec=BaseDeliveryProvider)
        mock_provider.get_provider_name.return_value = "MockSMSProvider"

        with patch("app.services.distribution.delivery_service.get_provider", return_value=mock_provider):
            processed, has_more = await process_job_batch(self.db, job.job_id, batch_size=10)

        # Provider send_message MUST NEVER be called
        mock_provider.send_message.assert_not_called()

        # Verify delivery record transitioned to FAILED with exact error code
        record = self.db.query(DeliveryRecord).filter(DeliveryRecord.job_id == job.id).first()
        assert record.delivery_status == DeliveryStatus.FAILED.value
        assert record.error_code == "CONTENT_NOT_APPROVED"

        # Verify diagnostic DeliveryAttempt was persisted
        attempt = self.db.query(DeliveryAttempt).filter(DeliveryAttempt.delivery_record_id == record.id).first()
        assert attempt is not None
        assert attempt.attempt_status == "failure"
        assert attempt.error_code == "CONTENT_NOT_APPROVED"

    @pytest.mark.asyncio
    async def test_worker_preflight_blocks_dispatch_when_content_modified_post_staging(self):
        """Invariant E: Worker pre-flight blocks dispatch if content copy was modified post-staging."""
        asset = self._create_sample_asset(review_status="Approved")
        self._create_clean_assessment(asset)
        camp = self._setup_distribution_campaign(asset)

        job = create_distribution_job(self.db, camp.id, "SMS", self.manager_user)

        # Tamper with content body directly
        asset.body = "Tampered body not covered by original audit."
        self.db.commit()

        mock_provider = MagicMock(spec=BaseDeliveryProvider)
        mock_provider.get_provider_name.return_value = "MockSMSProvider"

        with patch("app.services.distribution.delivery_service.get_provider", return_value=mock_provider):
            processed, has_more = await process_job_batch(self.db, job.job_id, batch_size=10)

        # Provider send_message MUST NEVER be called
        mock_provider.send_message.assert_not_called()

        record = self.db.query(DeliveryRecord).filter(DeliveryRecord.job_id == job.id).first()
        assert record.delivery_status == DeliveryStatus.FAILED.value
        assert record.error_code == "QUALITY_ASSESSMENT_STALE"

    @pytest.mark.asyncio
    async def test_multilingual_distribution_resolves_only_ready_variants(self):
        """Invariant E: Unassessed or critical translation variants are excluded from staging."""
        root_asset = self._create_sample_asset(review_status="Approved", body="English root content.")
        self._create_clean_assessment(root_asset)
        camp = self._setup_distribution_campaign(root_asset)

        # Create approved Tamil variant with NO assessment
        tamil_variant = ContentAsset(
            title="தமிழ் எச்சரிக்கை",
            body="தமிழ் உள்ளடக்கம்",
            category="Disaster Preparedness",
            tone="urgent",
            channel="SMS",
            source_language="en",
            target_language="ta",
            operation_type="translation",
            parent_id=root_asset.id,
            campaign_id=camp.id,
            review_status="Approved",
            created_by=self.manager_user.id,
        )
        self.db.add(tamil_variant)
        self.db.commit()

        # Recipient with Tamil preference
        m_tamil = AudienceMember(
            name="Meenakshi",
            email="meena@gov.in",
            phone="+919876543299",
            city="Madurai",
            preferred_language="ta",
            consent_status=True,
        )
        self.db.add(m_tamil)
        self.db.commit()

        # Update segment to include both
        seg = camp.segments[0]
        seg.filter_rules = {"combinator": "AND", "rules": [{"field": "city", "operator": "in", "value": ["Chennai", "Madurai"]}]}
        self.db.commit()

        # Create distribution job
        job = create_distribution_job(self.db, camp.id, "SMS", self.manager_user)
        records = self.db.query(DeliveryRecord).filter(DeliveryRecord.job_id == job.id).all()
        assert len(records) == 2

        # Meenakshi should gracefully fall back to English root because Tamil variant lacked assessment
        meena_rec = next(r for r in records if r.audience_member_id == m_tamil.id)
        assert meena_rec.rendered_content == "English root content."

    def test_reassessment_unblocks_approval_after_content_modification(self):
        """Invariant C: After content modification, running a fresh quality assessment unblocks approval."""
        asset = self._create_sample_asset(review_status="In Review", body="Initial message draft.")
        self._create_clean_assessment(asset)

        # Modify body
        asset.body = "Updated advisory copy with verified helpline 1070."
        self.db.commit()

        # Approval is blocked because assessment is stale
        payload = ContentReviewStatusUpdate(review_status="Approved", review_notes="Try approve stale")
        with pytest.raises(HTTPException) as exc_info:
            update_review_status(self.db, asset.id, payload, self.admin_user)
        assert exc_info.value.status_code == 400
        assert "modified since the last quality assessment" in exc_info.value.detail.lower()

        # Run fresh assessment with new content hash
        self._create_clean_assessment(asset)

        # Approval now succeeds
        payload_valid = ContentReviewStatusUpdate(review_status="Approved", review_notes="Approved after fresh audit")
        approved_asset = update_review_status(self.db, asset.id, payload_valid, self.admin_user)
        assert approved_asset.review_status == "Approved"

    @pytest.mark.asyncio
    async def test_invalid_channel_content_rejected_by_worker_preflight(self):
        """Invariant E: Worker pre-flight blocks dispatch for payload breaching channel hard limits."""
        # Create oversized body exceeding SMS 1600 character hard limit
        oversized_body = "Alert: " + ("A" * 1650)
        asset = self._create_sample_asset(review_status="Approved", body=oversized_body)
        self._create_clean_assessment(asset)
        camp = self._setup_distribution_campaign(asset)

        # Stage job (job staging creates records)
        job = DistributionJob(
            campaign_id=camp.id,
            content_asset_id=asset.id,
            channel="SMS",
            status=JobStatus.QUEUED.value,
            total_recipients=1,
            eligible_recipients=1,
            queued_recipients=1,
            created_by=self.manager_user.id,
        )
        self.db.add(job)
        self.db.flush()

        aud = camp.segments[0].audience_members[0] if getattr(camp.segments[0], "audience_members", None) else self.db.query(AudienceMember).first()
        record = DeliveryRecord(
            job_id=job.id,
            audience_member_id=aud.id,
            channel="SMS",
            recipient_address=aud.phone,
            delivery_status=DeliveryStatus.PENDING.value,
            rendered_content=oversized_body,
            idempotency_key=f"SMS-Oversized-{job.id}-{aud.id}",
        )
        self.db.add(record)
        self.db.commit()

        mock_provider = MagicMock(spec=BaseDeliveryProvider)
        mock_provider.get_provider_name.return_value = "MockSMSProvider"

        with patch("app.services.distribution.delivery_service.get_provider", return_value=mock_provider):
            await process_job_batch(self.db, job.job_id, batch_size=10)

        # Provider send_message MUST NEVER be called
        mock_provider.send_message.assert_not_called()

        self.db.refresh(record)
        assert record.delivery_status == DeliveryStatus.FAILED.value
        assert record.error_code == "PAYLOAD_EXCEEDS_CHANNEL_HARD_LIMIT"

    @pytest.mark.asyncio
    async def test_duplicate_delivery_attempt_preserves_idempotency(self):
        """Invariant E: Worker does not re-dispatch jobs or records already in terminal state."""
        asset = self._create_sample_asset(review_status="Approved")
        self._create_clean_assessment(asset)
        camp = self._setup_distribution_campaign(asset)

        job = create_distribution_job(self.db, camp.id, "SMS", self.manager_user)
        job.status = JobStatus.COMPLETED.value
        self.db.commit()

        mock_provider = MagicMock(spec=BaseDeliveryProvider)
        with patch("app.services.distribution.delivery_service.get_provider", return_value=mock_provider):
            processed, has_more = await process_job_batch(self.db, job.job_id, batch_size=10)

        assert processed == 0
        assert not has_more
        mock_provider.send_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_dynamic_critical_compliance_rule_blocks_approval_and_distribution(self):
        """
        Phase 1B integration: Admin-configured critical compliance rule dynamically blocks
        content approval and subsequent distribution job creation.
        """
        # Configure a dynamic critical rule
        rule = ComplianceRule(
            rule_code="COMP-BW-SEC-BLOCK",
            name="Emergency Block Term",
            rule_type="banned_word",
            pattern="unverified claim",
            severity="critical",
            is_global=True,
            created_by=self.admin_user.id,
        )
        self.db.add(rule)
        self.db.commit()

        # Create content asset with the prohibited term
        asset = self._create_sample_asset(
            review_status="Draft",
            body="Official Notice: This is an unverified claim regarding floods.",
        )

        # Run quality assessment
        assessment = await evaluate_content_asset(
            db=self.db,
            asset_id=asset.id,
            current_user=self.manager_user,
            provider_type="mock",
        )
        assert assessment.critical_issues_count >= 1
        assert assessment.overall_score <= 49.0

        # Attempt to approve -> MUST BE BLOCKED
        with pytest.raises(HTTPException) as exc_info:
            update_review_status(
                db=self.db,
                asset_id=asset.id,
                payload=ContentReviewStatusUpdate(
                    review_status="Approved",
                    review_notes="Bypass attempt.",
                ),
                current_user=self.manager_user,
            )
        assert exc_info.value.status_code == 400
        assert "blocked" in exc_info.value.detail.lower() or "critical" in exc_info.value.detail.lower()

        # Attempt to create distribution job -> MUST BE BLOCKED
        camp = self._setup_distribution_campaign(asset)
        with pytest.raises(HTTPException) as dist_exc:
            create_distribution_job(self.db, camp.id, "SMS", self.manager_user)
        assert dist_exc.value.status_code == 400
        assert "critical" in dist_exc.value.detail.lower() or "approved" in dist_exc.value.detail.lower()

