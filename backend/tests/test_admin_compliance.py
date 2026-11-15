"""
Test Suite: Admin-Managed Dynamic Compliance Rules & Engine Integration (Phase 1B)
Covers:
1. Admin CRUD APIs under /admin/compliance-rules (Create, List, Get, Update, Delete, Toggle).
2. Strict RBAC enforcement (Admin permitted; Manager, Author, and Unauthenticated forbidden).
3. Tenant isolation and organization scoping.
4. ReDoS protection and regex safety validation.
5. DeterministicRuleEngine evaluation of dynamic banned words, mandatory phrases, and regex patterns.
6. Quality assessment integration (POST /content/{id}/evaluate) and approval-blocking enforcement.
"""

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
from app.models.compliance_rule import ComplianceRule
from app.models.content_quality import ContentQualityAssessment, ContentQualityFinding
from app.schemas.content_asset import ContentReviewStatusUpdate
from app.services.quality.base import FindingCategory, FindingSeverity, ContentQualityFindingDTO
from app.services.quality.rule_engine import DeterministicRuleEngine
from app.services.quality_service import evaluate_content_asset, get_editorial_readiness
from app.services.content_service import update_review_status


class TestAdminCompliance:
    """Comprehensive test suite for Phase 1B Dynamic Compliance Rules."""

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

        # Seed Users with organization contexts
        self.super_admin = User(
            email="superadmin@gov.in",
            hashed_password=get_password_hash("AdminPass123!"),
            full_name="Super Admin",
            role_id=admin_role.id,
            organization=None,  # Platform global admin
            is_active=True,
        )
        self.health_admin = User(
            email="health_admin@gov.in",
            hashed_password=get_password_hash("AdminPass123!"),
            full_name="Health Admin",
            role_id=admin_role.id,
            organization="Public Health Department",
            is_active=True,
        )
        self.disaster_admin = User(
            email="disaster_admin@gov.in",
            hashed_password=get_password_hash("AdminPass123!"),
            full_name="Disaster Admin",
            role_id=admin_role.id,
            organization="Disaster Management Agency",
            is_active=True,
        )
        self.manager_user = User(
            email="manager@gov.in",
            hashed_password=get_password_hash("ManagerPass123!"),
            full_name="Campaign Manager",
            role_id=manager_role.id,
            organization="Public Health Department",
            is_active=True,
        )
        self.author_user = User(
            email="author@gov.in",
            hashed_password=get_password_hash("AuthorPass123!"),
            full_name="Author Officer",
            role_id=author_role.id,
            organization="Public Health Department",
            is_active=True,
        )
        self.db.add_all([
            self.super_admin,
            self.health_admin,
            self.disaster_admin,
            self.manager_user,
            self.author_user,
        ])
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

        self.super_admin_token = create_access_token(self.super_admin.id)
        self.health_admin_token = create_access_token(self.health_admin.id)
        self.disaster_admin_token = create_access_token(self.disaster_admin.id)
        self.manager_token = create_access_token(self.manager_user.id)
        self.author_token = create_access_token(self.author_user.id)

        yield

        app.dependency_overrides.clear()
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)

    def _headers(self, token: str) -> dict:
        return {"Authorization": f"Bearer {token}"}

    def _create_sample_asset(
        self,
        title: str = "Health Advisory",
        body: str = "Stay safe during monsoon.",
        channel: str = "Email",
        source_language: str = "en",
        creator_id: int = None,
        campaign_creator_org: str = None,
    ) -> ContentAsset:
        campaign = None
        if campaign_creator_org:
            creator = User(
                email=f"org_creator_{campaign_creator_org.replace(' ', '')}@gov.in",
                hashed_password=get_password_hash("Pass123!"),
                full_name="Org Creator",
                role_id=self.manager_user.role_id,
                organization=campaign_creator_org,
                is_active=True,
            )
            self.db.add(creator)
            self.db.commit()

            campaign = Campaign(
                name="Advisory Campaign",
                campaign_type="Awareness",
                created_by=creator.id,
            )
            self.db.add(campaign)
            self.db.commit()

        asset = ContentAsset(
            title=title,
            body=body,
            category="Healthcare",
            tone="informative",
            channel=channel,
            source_language=source_language,
            created_by=creator_id or self.author_user.id,
            campaign_id=campaign.id if campaign else None,
            review_status="Draft",
        )
        self.db.add(asset)
        self.db.commit()
        self.db.refresh(asset)
        return asset

    # =========================================================================
    # 1. CRUD API TESTS
    # =========================================================================

    def test_create_banned_word_rule_success(self):
        """Admin successfully creates a dynamic banned word compliance rule."""
        payload = {
            "name": "Banned Unverified Cure",
            "description": "Prohibits fraudulent medical claims",
            "rule_type": "banned_word",
            "pattern": "secret cure",
            "severity": "critical",
            "is_global": True,
            "suggested_action": "Use verified medical terminology.",
        }
        res = self.client.post(
            "/admin/compliance-rules",
            json=payload,
            headers=self._headers(self.super_admin_token),
        )
        assert res.status_code == 201
        data = res.json()
        assert data["name"] == "Banned Unverified Cure"
        assert data["rule_type"] == "banned_word"
        assert data["pattern"] == "secret cure"
        assert data["severity"] == "critical"
        assert data["is_global"] is True
        assert data["is_active"] is True
        assert data["rule_code"].startswith("COMP-BW-")
        assert data["created_by"] == self.super_admin.id

    def test_create_mandatory_phrase_rule_success(self):
        """Admin creates a mandatory disclaimer compliance rule."""
        payload = {
            "rule_code": "COMP-MP-GOV-001",
            "name": "Government Official Notice Disclaimer",
            "rule_type": "mandatory_phrase",
            "pattern": "Issued in Public Interest by Government",
            "severity": "high",
            "channel": "SMS",
            "is_global": True,
        }
        res = self.client.post(
            "/admin/compliance-rules",
            json=payload,
            headers=self._headers(self.super_admin_token),
        )
        assert res.status_code == 201
        data = res.json()
        assert data["rule_code"] == "COMP-MP-GOV-001"
        assert data["channel"] == "SMS"
        assert data["severity"] == "high"

    def test_create_regex_rule_success(self):
        """Admin creates a regex pattern compliance rule."""
        payload = {
            "name": "Credit Card Mask Rule",
            "rule_type": "regex_pattern",
            "pattern": r"\b(?:\d{4}[-\s]?){3}\d{4}\b",
            "severity": "critical",
            "is_global": True,
        }
        res = self.client.post(
            "/admin/compliance-rules",
            json=payload,
            headers=self._headers(self.super_admin_token),
        )
        assert res.status_code == 201
        assert res.json()["rule_type"] == "regex_pattern"

    def test_create_rule_duplicate_code_rejected(self):
        """Creating a rule with a duplicate rule code returns 409 Conflict."""
        payload = {
            "rule_code": "COMP-DUP-001",
            "name": "First Rule",
            "rule_type": "banned_word",
            "pattern": "fraudulent term",
            "severity": "medium",
            "is_global": True,
        }
        res1 = self.client.post("/admin/compliance-rules", json=payload, headers=self._headers(self.super_admin_token))
        assert res1.status_code == 201

        # Second rule with same code
        payload2 = {
            "rule_code": "COMP-DUP-001",
            "name": "Second Rule",
            "rule_type": "banned_word",
            "pattern": "different term",
            "severity": "low",
            "is_global": True,
        }
        res2 = self.client.post("/admin/compliance-rules", json=payload2, headers=self._headers(self.super_admin_token))
        assert res2.status_code == 409
        assert "already exists" in res2.json()["detail"].lower()

    def test_create_rule_duplicate_pattern_in_same_scope_rejected(self):
        """Creating duplicate pattern within identical scope returns 409 Conflict."""
        payload = {
            "name": "Duplicate Pattern Rule",
            "rule_type": "banned_word",
            "pattern": "banned token",
            "severity": "critical",
            "is_global": True,
        }
        res1 = self.client.post("/admin/compliance-rules", json=payload, headers=self._headers(self.super_admin_token))
        assert res1.status_code == 201

        res2 = self.client.post("/admin/compliance-rules", json=payload, headers=self._headers(self.super_admin_token))
        assert res2.status_code == 409
        assert "identical pattern" in res2.json()["detail"].lower()

    def test_create_rule_invalid_regex_rejected(self):
        """Invalid regex syntax returns 422 Unprocessable Entity."""
        payload = {
            "name": "Broken Regex",
            "rule_type": "regex_pattern",
            "pattern": "[a-z",  # unclosed character class
            "severity": "critical",
            "is_global": True,
        }
        res = self.client.post("/admin/compliance-rules", json=payload, headers=self._headers(self.super_admin_token))
        assert res.status_code == 422

    def test_create_rule_redos_pattern_rejected(self):
        """Suspected ReDoS nested quantifier regex is safely rejected with 422."""
        payload = {
            "name": "Evil ReDoS Regex",
            "rule_type": "regex_pattern",
            "pattern": r"(a+)+",
            "severity": "critical",
            "is_global": True,
        }
        res = self.client.post("/admin/compliance-rules", json=payload, headers=self._headers(self.super_admin_token))
        assert res.status_code == 422
        assert "catastrophic backtracking" in str(res.json()).lower()

    def test_list_rules_with_pagination_and_filters(self):
        """List compliance rules with pagination, rule_type, severity, and search filters."""
        # Seed 3 rules
        r1 = ComplianceRule(
            rule_code="COMP-BW-SEARCH-1",
            name="Searchable Toxic Term",
            rule_type="banned_word",
            pattern="toxic_phrase",
            severity="critical",
            is_global=True,
            created_by=self.super_admin.id,
        )
        r2 = ComplianceRule(
            rule_code="COMP-MP-SEARCH-2",
            name="Searchable Helpline Phrase",
            rule_type="mandatory_phrase",
            pattern="Call 104 Helpline",
            severity="high",
            channel="SMS",
            is_global=True,
            created_by=self.super_admin.id,
        )
        r3 = ComplianceRule(
            rule_code="COMP-BW-SEARCH-3",
            name="Another Banned Phrase",
            rule_type="banned_word",
            pattern="forbidden_word",
            severity="low",
            is_active=False,
            is_global=True,
            created_by=self.super_admin.id,
        )
        self.db.add_all([r1, r2, r3])
        self.db.commit()

        # 1. Pagination check
        res = self.client.get(
            "/admin/compliance-rules?page=1&size=2",
            headers=self._headers(self.super_admin_token),
        )
        assert res.status_code == 200
        body = res.json()
        assert body["total"] == 3
        assert len(body["items"]) == 2
        assert body["page"] == 1
        assert body["pages"] == 2

        # 2. Filter by rule_type
        res_type = self.client.get(
            "/admin/compliance-rules?rule_type=mandatory_phrase",
            headers=self._headers(self.super_admin_token),
        )
        assert res_type.status_code == 200
        items = res_type.json()["items"]
        assert len(items) == 1
        assert items[0]["rule_code"] == "COMP-MP-SEARCH-2"

        # 3. Filter by is_active
        res_active = self.client.get(
            "/admin/compliance-rules?is_active=false",
            headers=self._headers(self.super_admin_token),
        )
        assert res_active.status_code == 200
        assert len(res_active.json()["items"]) == 1
        assert res_active.json()["items"][0]["rule_code"] == "COMP-BW-SEARCH-3"

        # 4. Search query
        res_search = self.client.get(
            "/admin/compliance-rules?search=Helpline",
            headers=self._headers(self.super_admin_token),
        )
        assert res_search.status_code == 200
        assert len(res_search.json()["items"]) == 1
        assert "Helpline" in res_search.json()["items"][0]["name"]

    def test_get_rule_by_id(self):
        """Retrieve single compliance rule by ID; 404 for missing rule."""
        rule = ComplianceRule(
            rule_code="COMP-BW-GET-01",
            name="Single Fetch Rule",
            rule_type="banned_word",
            pattern="test token",
            severity="medium",
            is_global=True,
            created_by=self.super_admin.id,
        )
        self.db.add(rule)
        self.db.commit()

        res = self.client.get(f"/admin/compliance-rules/{rule.id}", headers=self._headers(self.super_admin_token))
        assert res.status_code == 200
        assert res.json()["rule_code"] == "COMP-BW-GET-01"

        res_404 = self.client.get("/admin/compliance-rules/99999", headers=self._headers(self.super_admin_token))
        assert res_404.status_code == 404

    def test_update_rule_fields(self):
        """Update compliance rule attributes via PATCH."""
        rule = ComplianceRule(
            rule_code="COMP-BW-UPD-01",
            name="Initial Name",
            rule_type="banned_word",
            pattern="initial pattern",
            severity="low",
            is_global=True,
            created_by=self.super_admin.id,
        )
        self.db.add(rule)
        self.db.commit()

        update_payload = {
            "name": "Updated Name",
            "severity": "critical",
            "pattern": "modified pattern",
            "suggested_action": "Check guidance",
        }
        res = self.client.patch(
            f"/admin/compliance-rules/{rule.id}",
            json=update_payload,
            headers=self._headers(self.super_admin_token),
        )
        assert res.status_code == 200
        data = res.json()
        assert data["name"] == "Updated Name"
        assert data["severity"] == "critical"
        assert data["pattern"] == "modified pattern"
        assert data["suggested_action"] == "Check guidance"
        assert data["updated_by"] == self.super_admin.id

    def test_toggle_rule_active(self):
        """Toggle compliance rule active status."""
        rule = ComplianceRule(
            rule_code="COMP-BW-TOGGLE-01",
            name="Toggle Rule",
            rule_type="banned_word",
            pattern="toggle pattern",
            severity="high",
            is_active=True,
            is_global=True,
            created_by=self.super_admin.id,
        )
        self.db.add(rule)
        self.db.commit()

        # Toggle to False
        res1 = self.client.patch(f"/admin/compliance-rules/{rule.id}/toggle-active", headers=self._headers(self.super_admin_token))
        assert res1.status_code == 200
        assert res1.json()["is_active"] is False

        # Toggle back to True
        res2 = self.client.patch(f"/admin/compliance-rules/{rule.id}/toggle-active", headers=self._headers(self.super_admin_token))
        assert res2.status_code == 200
        assert res2.json()["is_active"] is True

    def test_delete_rule(self):
        """Delete compliance rule permanently."""
        rule = ComplianceRule(
            rule_code="COMP-BW-DEL-01",
            name="Rule to Delete",
            rule_type="banned_word",
            pattern="delete pattern",
            severity="low",
            is_global=True,
            created_by=self.super_admin.id,
        )
        self.db.add(rule)
        self.db.commit()

        res = self.client.delete(f"/admin/compliance-rules/{rule.id}", headers=self._headers(self.super_admin_token))
        assert res.status_code == 200
        assert "successfully deleted" in res.json()["detail"].lower()

        # Verify 404 on fetch
        res_get = self.client.get(f"/admin/compliance-rules/{rule.id}", headers=self._headers(self.super_admin_token))
        assert res_get.status_code == 404

    # =========================================================================
    # 2. RBAC & TENANT ISOLATION TESTS
    # =========================================================================

    def test_unauthenticated_requests_rejected(self):
        """Requests without Authorization header are rejected with 401 Unauthorized."""
        res_get = self.client.get("/admin/compliance-rules")
        assert res_get.status_code == 401

        res_post = self.client.post("/admin/compliance-rules", json={"name": "test", "rule_type": "banned_word", "pattern": "a"})
        assert res_post.status_code == 401

    def test_campaign_manager_forbidden(self):
        """Campaign Managers cannot access admin compliance endpoints (403 Forbidden)."""
        res_get = self.client.get("/admin/compliance-rules", headers=self._headers(self.manager_token))
        assert res_get.status_code == 403

        res_post = self.client.post(
            "/admin/compliance-rules",
            json={"name": "test", "rule_type": "banned_word", "pattern": "a"},
            headers=self._headers(self.manager_token),
        )
        assert res_post.status_code == 403

    def test_author_forbidden(self):
        """Communication Team authors cannot access admin compliance endpoints (403 Forbidden)."""
        res_get = self.client.get("/admin/compliance-rules", headers=self._headers(self.author_token))
        assert res_get.status_code == 403

    def test_cross_organization_rule_access_forbidden(self):
        """Admin from Health Dept cannot create or access rules for Disaster Agency."""
        # Health admin tries to create rule for Disaster Agency
        payload = {
            "name": "Disaster Rule Spoofed",
            "rule_type": "banned_word",
            "pattern": "disaster test",
            "severity": "critical",
            "organization": "Disaster Management Agency",
        }
        res_create = self.client.post(
            "/admin/compliance-rules",
            json=payload,
            headers=self._headers(self.health_admin_token),
        )
        assert res_create.status_code == 403
        assert "cannot create rules for organization" in res_create.json()["detail"].lower()

        # Seed private Disaster rule
        disaster_rule = ComplianceRule(
            rule_code="COMP-DISASTER-01",
            name="Disaster Secret Rule",
            rule_type="banned_word",
            pattern="disaster only",
            organization="Disaster Management Agency",
            is_global=False,
            created_by=self.disaster_admin.id,
        )
        self.db.add(disaster_rule)
        self.db.commit()

        # Health admin tries to fetch Disaster rule
        res_fetch = self.client.get(
            f"/admin/compliance-rules/{disaster_rule.id}",
            headers=self._headers(self.health_admin_token),
        )
        assert res_fetch.status_code == 403

        # Health admin list should not leak Disaster rule
        res_list = self.client.get("/admin/compliance-rules", headers=self._headers(self.health_admin_token))
        assert res_list.status_code == 200
        codes = [item["rule_code"] for item in res_list.json()["items"]]
        assert "COMP-DISASTER-01" not in codes

    # =========================================================================
    # 3. RULE ENGINE UNIT TESTS
    # =========================================================================

    def test_dynamic_banned_word_detection(self):
        """DeterministicRuleEngine correctly matches banned word case-insensitively on word boundaries."""
        rule = ComplianceRule(
            rule_code="COMP-BW-TEST-01",
            name="Banned Term Riot",
            rule_type="banned_word",
            pattern="riot",
            severity="critical",
            is_global=True,
            created_by=self.super_admin.id,
        )

        # 1. Offending text has exact word
        findings_hit = DeterministicRuleEngine.evaluate(
            title="Notice",
            body="Citizens were involved in a massive riot yesterday.",
            call_to_action="Stay safe",
            channel="Email",
            source_language="en",
            compliance_rules=[rule],
        )
        bw_hits = [f for f in findings_hit if f.rule_id == "COMP-BW-TEST-01"]
        assert len(bw_hits) == 1
        assert bw_hits[0].severity == FindingSeverity.CRITICAL
        assert bw_hits[0].affected_text.lower() == "riot"

        # 2. Case-insensitive match ("Riot")
        findings_case = DeterministicRuleEngine.evaluate(
            title="Notice",
            body="Avoid the Riot area immediately.",
            call_to_action=None,
            channel="Email",
            source_language="en",
            compliance_rules=[rule],
        )
        assert any(f.rule_id == "COMP-BW-TEST-01" for f in findings_case)

        # 3. Substring non-match ("patriotic" should NOT match "riot")
        findings_safe = DeterministicRuleEngine.evaluate(
            title="Notice",
            body="Be patriotic and follow traffic guidelines.",
            call_to_action=None,
            channel="Email",
            source_language="en",
            compliance_rules=[rule],
        )
        assert not any(f.rule_id == "COMP-BW-TEST-01" for f in findings_safe)

    def test_dynamic_mandatory_phrase_detection(self):
        """DeterministicRuleEngine verifies mandatory phrase presence."""
        rule = ComplianceRule(
            rule_code="COMP-MP-TEST-01",
            name="Emergency Toll-Free Helpline",
            rule_type="mandatory_phrase",
            pattern="Call 1070 for Emergency Relief",
            severity="high",
            is_global=True,
            created_by=self.super_admin.id,
        )

        # 1. Missing phrase produces high-severity finding
        findings_missing = DeterministicRuleEngine.evaluate(
            title="Flood Advisory",
            body="Stay indoors during water accumulation.",
            call_to_action=None,
            channel="SMS",
            source_language="en",
            compliance_rules=[rule],
        )
        mp_findings = [f for f in findings_missing if f.rule_id == "COMP-MP-TEST-01"]
        assert len(mp_findings) == 1
        assert mp_findings[0].severity == FindingSeverity.HIGH
        assert "Call 1070 for Emergency Relief" in mp_findings[0].explanation

        # 2. Present phrase satisfies rule (no finding)
        findings_present = DeterministicRuleEngine.evaluate(
            title="Flood Advisory",
            body="Stay indoors. Call 1070 for Emergency Relief immediately.",
            call_to_action=None,
            channel="SMS",
            source_language="en",
            compliance_rules=[rule],
        )
        assert not any(f.rule_id == "COMP-MP-TEST-01" for f in findings_present)

    def test_inactive_rule_ignored_by_engine(self):
        """Inactive compliance rules produce zero findings."""
        rule = ComplianceRule(
            rule_code="COMP-INACTIVE-01",
            name="Deactivated Rule",
            rule_type="banned_word",
            pattern="forbidden_word",
            severity="critical",
            is_active=False,
            is_global=True,
            created_by=self.super_admin.id,
        )
        findings = DeterministicRuleEngine.evaluate(
            title="Notice",
            body="This text has forbidden_word in it.",
            call_to_action=None,
            channel="Email",
            source_language="en",
            compliance_rules=[rule],
        )
        assert not any(f.rule_id == "COMP-INACTIVE-01" for f in findings)

    def test_channel_and_language_filtering_in_engine(self):
        """Channel and language constraints properly isolate rules in the engine."""
        sms_rule = ComplianceRule(
            rule_code="COMP-CHAN-SMS-01",
            name="SMS Specific Disclaimer",
            rule_type="mandatory_phrase",
            pattern="Txt STOP to Opt-out",
            severity="medium",
            channel="SMS",
            is_global=True,
            created_by=self.super_admin.id,
        )
        hindi_rule = ComplianceRule(
            rule_code="COMP-LANG-HI-01",
            name="Hindi Disclaimer",
            rule_type="mandatory_phrase",
            pattern="जनहित में जारी",
            severity="medium",
            language="hi",
            is_global=True,
            created_by=self.super_admin.id,
        )

        # Evaluating Email / English content: neither SMS nor Hindi rule should trigger
        findings_email = DeterministicRuleEngine.evaluate(
            title="Official Update",
            body="Normal announcement copy.",
            call_to_action=None,
            channel="Email",
            source_language="en",
            compliance_rules=[sms_rule, hindi_rule],
        )
        assert not any(f.rule_id in ("COMP-CHAN-SMS-01", "COMP-LANG-HI-01") for f in findings_email)

        # Evaluating SMS / English: only SMS rule triggers
        findings_sms = DeterministicRuleEngine.evaluate(
            title="Official Update",
            body="Normal announcement copy.",
            call_to_action=None,
            channel="SMS",
            source_language="en",
            compliance_rules=[sms_rule, hindi_rule],
        )
        assert any(f.rule_id == "COMP-CHAN-SMS-01" for f in findings_sms)
        assert not any(f.rule_id == "COMP-LANG-HI-01" for f in findings_sms)

    def test_deduplication_with_builtin_panic_words(self):
        """Admin-configured rule on panic word supersedes duplicate built-in panic word finding."""
        # Built-in engine has "everyone will die" as RULE-SAFE-001
        admin_rule = ComplianceRule(
            rule_code="COMP-BW-CUSTOM-PANIC",
            name="Department Panic Policy",
            rule_type="banned_word",
            pattern="everyone will die",
            severity="critical",
            suggested_action="Use calm citizen guidance.",
            is_global=True,
            created_by=self.super_admin.id,
        )
        findings = DeterministicRuleEngine.evaluate(
            title="Severe Storm Warning",
            body="Seek immediate shelter or everyone will die right now.",
            call_to_action=None,
            channel="Email",
            source_language="en",
            compliance_rules=[admin_rule],
        )
        # Should have exactly one finding for this phrase, attributed to COMP-BW-CUSTOM-PANIC
        custom_findings = [f for f in findings if f.rule_id == "COMP-BW-CUSTOM-PANIC"]
        builtin_duplicates = [f for f in findings if f.rule_id == "RULE-SAFE-001" and f.affected_text and "everyone will die" in f.affected_text.lower()]
        assert len(custom_findings) == 1
        assert len(builtin_duplicates) == 0

    # =========================================================================
    # 4. QUALITY ASSESSMENT & APPROVAL INTEGRATION TESTS
    # =========================================================================

    @pytest.mark.asyncio
    async def test_evaluate_content_persists_dynamic_findings_and_blocks_approval(self):
        """
        POST /content/{id}/evaluate loads dynamic rules, persists findings,
        caps overall score, and blocks editorial approval (Phase 1A invariant).
        """
        # 1. Seed critical banned-word rule
        rule = ComplianceRule(
            rule_code="COMP-BW-UNVERIFIED-01",
            name="Unverified Miracle Claim",
            rule_type="banned_word",
            pattern="guaranteed miracle cure",
            severity="critical",
            suggested_action="Remove unverified claims.",
            is_global=True,
            created_by=self.super_admin.id,
        )
        self.db.add(rule)
        self.db.commit()

        # 2. Create asset containing the banned phrase
        asset = self._create_sample_asset(
            title="Dengue Alert",
            body="Use our herbal tonic as a guaranteed miracle cure against high fever.",
            channel="Email",
        )

        # 3. Execute quality evaluation via service layer
        assessment_res = await evaluate_content_asset(
            db=self.db,
            asset_id=asset.id,
            current_user=self.manager_user,
            provider_type="mock",
        )
        assert assessment_res.overall_score <= 49.0
        assert assessment_res.status in ("completed_with_warnings", "failed")
        assert assessment_res.critical_issues_count >= 1

        # Verify finding was persisted in database
        persisted_findings = self.db.query(ContentQualityFinding).filter(
            ContentQualityFinding.assessment_id == assessment_res.id,
            ContentQualityFinding.rule_id == "COMP-BW-UNVERIFIED-01",
        ).all()
        assert len(persisted_findings) == 1
        assert persisted_findings[0].affected_text.lower() == "guaranteed miracle cure"

        # 4. Attempt to approve content via content_service -> MUST FAIL
        with pytest.raises(HTTPException) as exc_info:
            update_review_status(
                db=self.db,
                asset_id=asset.id,
                payload=ContentReviewStatusUpdate(
                    review_status="Approved",
                    review_notes="Attempted bypass with critical compliance violation.",
                ),
                current_user=self.manager_user,
            )
        assert exc_info.value.status_code == 400
        assert "critical" in exc_info.value.detail.lower() or "blocked" in exc_info.value.detail.lower()

        # Verify asset remains in Draft status
        self.db.refresh(asset)
        assert asset.review_status == "Draft"

    @pytest.mark.asyncio
    async def test_re_evaluation_compliant_enables_approval(self):
        """Fixing content removes dynamic violation, raises score, and permits approval."""
        rule = ComplianceRule(
            rule_code="COMP-BW-RESTRICTED-02",
            name="Restricted Term",
            rule_type="banned_word",
            pattern="unauthorized medicine",
            severity="critical",
            is_global=True,
            created_by=self.super_admin.id,
        )
        self.db.add(rule)
        self.db.commit()

        # Asset starts non-compliant
        asset = self._create_sample_asset(
            title="Medical Notice",
            body="Do not distribute unauthorized medicine in wards.",
            channel="Email",
        )

        # First evaluation: fails
        res1 = await evaluate_content_asset(
            db=self.db,
            asset_id=asset.id,
            current_user=self.manager_user,
            provider_type="mock",
        )
        assert res1.critical_issues_count >= 1

        # Remediate copy: remove offending term
        asset.body = "Do not distribute unverified medicines in wards. Follow standard medical protocols."
        self.db.commit()

        # Re-evaluate
        res2 = await evaluate_content_asset(
            db=self.db,
            asset_id=asset.id,
            current_user=self.manager_user,
            provider_type="mock",
        )
        assert res2.critical_issues_count == 0
        assert res2.overall_score >= 70.0

        # Now approve -> MUST SUCCEED
        approved_asset = update_review_status(
            db=self.db,
            asset_id=asset.id,
            payload=ContentReviewStatusUpdate(
                review_status="Approved",
                review_notes="Compliant with all department rules.",
            ),
            current_user=self.manager_user,
        )
        assert approved_asset.review_status == "Approved"

    @pytest.mark.asyncio
    async def test_organization_rule_isolation_in_quality_evaluation(self):
        """
        Organization-specific rule for Public Health Department does NOT affect
        Disaster Management Agency content.
        """
        # Create private rule for Public Health Department only
        health_rule = ComplianceRule(
            rule_code="COMP-HEALTH-ONLY",
            name="Health Dept Disclaimer Required",
            rule_type="mandatory_phrase",
            pattern="Health Dept Advisory Seal",
            severity="critical",
            organization="Public Health Department",
            is_global=False,
            created_by=self.health_admin.id,
        )
        self.db.add(health_rule)
        self.db.commit()

        # Create asset belonging to Disaster Management Agency
        disaster_asset = self._create_sample_asset(
            title="Flood Alert",
            body="Move to high ground immediately.",
            channel="Email",
            campaign_creator_org="Disaster Management Agency",
        )

        # Evaluate Disaster asset
        res_disaster = await evaluate_content_asset(
            db=self.db,
            asset_id=disaster_asset.id,
            current_user=self.manager_user,
            provider_type="mock",
        )
        # Health Dept rule should NOT apply to Disaster Agency asset
        assert not any(f.rule_id == "COMP-HEALTH-ONLY" for f in res_disaster.findings)
        assert res_disaster.critical_issues_count == 0

        # Create asset belonging to Public Health Department
        health_asset = self._create_sample_asset(
            title="Immunization Drive",
            body="Free vaccination camps open tomorrow.",
            channel="Email",
            campaign_creator_org="Public Health Department",
        )

        # Evaluate Health asset
        res_health = await evaluate_content_asset(
            db=self.db,
            asset_id=health_asset.id,
            current_user=self.manager_user,
            provider_type="mock",
        )
        # Health Dept rule MUST apply
        assert any(f.rule_id == "COMP-HEALTH-ONLY" for f in res_health.findings)
        assert res_health.critical_issues_count >= 1

