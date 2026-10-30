"""Comprehensive automated test suite for Task 6, Checkpoint 1: Backend Foundation."""

import unittest
from datetime import datetime, timezone, timedelta
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi import HTTPException

from app.db.base import Base
from app.db.seed import seed_default_roles, seed_default_templates
from app.models.user import User
from app.models.template import Template
from app.models.campaign import Campaign
from app.models.segment import Segment
from app.models.audience import AudienceMember
from app.core.security import get_password_hash
from app.schemas.template import (
    TemplateCreate,
    TemplateUpdate,
    validate_placeholders,
    ALLOWED_PLACEHOLDERS,
)
from app.schemas.campaign import (
    CampaignCreate,
    CampaignUpdate,
    CampaignStatusUpdate,
)
from app.services.template_service import (
    create_template,
    list_templates,
    get_template_by_id,
    get_template_response,
    update_template,
    delete_template,
)
from app.services.campaign_service import (
    create_campaign,
    list_campaigns,
    get_campaign_by_id,
    get_campaign_response,
    update_campaign,
    delete_campaign,
    transition_campaign_status,
    calculate_campaign_reach,
    render_campaign_preview,
)


class TestCampaignBackendFoundation(unittest.TestCase):
    """Test suite for Campaign & Template Schemas, Services, Reach, Consent, and Seeding."""

    @classmethod
    def setUpClass(cls):
        cls.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        cls.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=cls.engine)

    def setUp(self):
        Base.metadata.create_all(bind=self.engine)
        self.db = self.SessionLocal()
        roles = seed_default_roles(self.db)
        self.admin_role = roles["Admin"]
        self.manager_role = roles["Campaign Manager"]
        self.comm_role = roles["Communication Team"]

        # Users
        self.admin_user = User(
            full_name="Admin Director",
            email="admin.director@agency.gov.in",
            hashed_password=get_password_hash("AdminPass123!"),
            role_id=self.admin_role.id,
            is_active=True,
        )
        self.manager_user = User(
            full_name="Campaign Manager 1",
            email="manager1@agency.gov.in",
            hashed_password=get_password_hash("ManagerPass123!"),
            role_id=self.manager_role.id,
            is_active=True,
        )
        self.other_manager = User(
            full_name="Campaign Manager 2",
            email="manager2@agency.gov.in",
            hashed_password=get_password_hash("Manager2Pass123!"),
            role_id=self.manager_role.id,
            is_active=True,
        )
        self.comm_user = User(
            full_name="Comm Staff",
            email="comm.staff@agency.gov.in",
            hashed_password=get_password_hash("CommPass123!"),
            role_id=self.comm_role.id,
            is_active=True,
        )
        self.db.add_all([self.admin_user, self.manager_user, self.other_manager, self.comm_user])
        self.db.commit()

        # Seed Audience Members with varied language, city, and tri-state consent
        # 1. Aarav (Delhi, hi, consent=True)
        self.aud_aarav = AudienceMember(
            name="Aarav Sharma",
            email="aarav.sharma@example.gov.in",
            phone="+919876543210",
            age=65,
            city="New Delhi",
            state="Delhi",
            preferred_language="hi",
            preferred_channel="email",
            occupation="Civilian",
            organization_department="Public Health",
            consent_status=True,
        )
        # 2. Priya (Delhi, hi, consent=None / Unconfirmed)
        self.aud_priya = AudienceMember(
            name="Priya Verma",
            email="priya.verma@example.gov.in",
            phone="+919876543211",
            age=28,
            city="New Delhi",
            state="Delhi",
            preferred_language="hi",
            preferred_channel="sms",
            occupation="Teacher",
            organization_department="Education",
            consent_status=None,
        )
        # 3. Karthik (Chennai, ta, consent=True)
        self.aud_karthik = AudienceMember(
            name="Karthik Raman",
            email="karthik.raman@example.gov.in",
            phone="+919876543212",
            age=40,
            city="Chennai",
            state="Tamil Nadu",
            preferred_language="ta",
            preferred_channel="whatsapp",
            occupation="Engineer",
            organization_department="Municipal Works",
            consent_status=True,
        )
        # 4. Ananya (Kolkata, bn, consent=False / Revoked)
        self.aud_ananya = AudienceMember(
            name="Ananya Sen",
            email="ananya.sen@example.gov.in",
            phone="+919876543213",
            age=35,
            city="Kolkata",
            state="West Bengal",
            preferred_language="bn",
            preferred_channel="email",
            occupation="Doctor",
            organization_department="Healthcare",
            consent_status=False,
        )
        self.db.add_all([self.aud_aarav, self.aud_priya, self.aud_karthik, self.aud_ananya])
        self.db.commit()

        # Seed two segments with overlapping audience
        # Segment 1: Delhi residents (Aarav, Priya)
        self.seg_delhi = Segment(
            name="Delhi Residents",
            description="All Delhi recipients",
            filter_rules={
                "connector": "AND",
                "conditions": [{"field": "state", "operator": "equals", "value": "Delhi"}],
            },
            created_by=self.manager_user.id,
        )
        # Segment 2: Hindi speakers (Aarav, Priya) -> completely overlaps with Delhi in this test data
        self.seg_hindi = Segment(
            name="Hindi Speakers",
            description="Hindi language recipients",
            filter_rules={
                "connector": "AND",
                "conditions": [{"field": "preferred_language", "operator": "equals", "value": "hi"}],
            },
            created_by=self.manager_user.id,
        )
        # Segment 3: Tamil speakers (Karthik)
        self.seg_tamil = Segment(
            name="Tamil Speakers",
            description="Tamil language recipients",
            filter_rules={
                "connector": "AND",
                "conditions": [{"field": "preferred_language", "operator": "equals", "value": "ta"}],
            },
            created_by=self.manager_user.id,
        )
        self.db.add_all([self.seg_delhi, self.seg_hindi, self.seg_tamil])
        self.db.commit()

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)

    # =========================================================================
    # 1. Template Placeholder Validation Tests
    # =========================================================================

    def test_placeholder_validation_valid_and_unsupported(self):
        """Test valid placeholders pass while unsupported or malformed placeholders are rejected."""
        valid_text = "Hello {name}, welcome to {city}, {state}. Language: {preferred_language}."
        placeholders = validate_placeholders(valid_text)
        self.assertEqual(placeholders, ["{city}", "{name}", "{preferred_language}", "{state}"])

        # Unsupported placeholder
        with self.assertRaises(ValueError) as ctx:
            validate_placeholders("Your account balance is {account_balance}.")
        self.assertIn("Unsupported placeholder", str(ctx.exception))

        # Empty placeholder {}
        with self.assertRaises(ValueError) as ctx:
            validate_placeholders("Notice to all {} citizens.")
        self.assertIn("empty placeholder", str(ctx.exception))

        # Mismatched unclosed braces
        with self.assertRaises(ValueError) as ctx:
            validate_placeholders("Dear {name, please visit the portal.")
        self.assertIn("Mismatched placeholder braces", str(ctx.exception))

        # Malformed syntax with spaces or hyphens inside braces
        with self.assertRaises(ValueError) as ctx:
            validate_placeholders("Dear {name and city}, greetings.")
        self.assertIn("Malformed placeholder syntax", str(ctx.exception))

    # =========================================================================
    # 2. Template Schema & Service Tests
    # =========================================================================

    def test_template_crud_and_duplicate_titles(self):
        """Test template creation, retrieval, listing, partial update, and title uniqueness."""
        data = TemplateCreate(
            title="Clean Water Advisory",
            category="Healthcare",
            body="Dear {name}, boiling water notice in {city}, {state}.",
            language="en",
            tags="water,health",
        )
        resp = create_template(self.db, data, self.manager_user)
        self.assertEqual(resp.title, "Clean Water Advisory")
        self.assertEqual(resp.created_by, self.manager_user.id)
        self.assertEqual(resp.placeholders, ["{city}", "{name}", "{state}"])

        # Duplicate title rejection (case-insensitive)
        dup_data = TemplateCreate(
            title="clean water advisory",
            category="Healthcare",
            body="Another body text for {name}.",
        )
        with self.assertRaises(HTTPException) as ctx:
            create_template(self.db, dup_data, self.admin_user)
        self.assertEqual(ctx.exception.status_code, 409)

        # Retrieval
        fetched = get_template_response(self.db, resp.id)
        self.assertEqual(fetched.id, resp.id)
        self.assertEqual(fetched.creator_name, "Campaign Manager 1")

        # List & filtering
        listed = list_templates(self.db, page=1, page_size=10, category="Healthcare")
        self.assertEqual(listed.total, 1)
        self.assertEqual(listed.items[0].id, resp.id)

        # Update by owner
        update_data = TemplateUpdate(title="Clean Water & Sanitation Advisory", tags="water,health,sanitation")
        updated = update_template(self.db, resp.id, update_data, self.manager_user)
        self.assertEqual(updated.title, "Clean Water & Sanitation Advisory")

        # Delete by owner
        delete_template(self.db, resp.id, self.manager_user)
        with self.assertRaises(HTTPException) as ctx:
            get_template_by_id(self.db, resp.id)
        self.assertEqual(ctx.exception.status_code, 404)

    def test_template_manager_ownership_restrictions(self):
        """Ensure Campaign Managers cannot edit or delete templates created by other managers."""
        tmpl = create_template(
            self.db,
            TemplateCreate(
                title="Manager 1 Template",
                category="Civic Education",
                body="Civic notice for {name} in {city}.",
            ),
            self.manager_user,
        )

        # Manager 2 attempts to update Manager 1's template -> 403
        with self.assertRaises(HTTPException) as ctx:
            update_template(self.db, tmpl.id, TemplateUpdate(title="Hacked Title"), self.other_manager)
        self.assertEqual(ctx.exception.status_code, 403)

        # Manager 2 attempts to delete Manager 1's template -> 403
        with self.assertRaises(HTTPException) as ctx:
            delete_template(self.db, tmpl.id, self.other_manager)
        self.assertEqual(ctx.exception.status_code, 403)

        # Admin can update and delete any template -> Succeeds
        admin_updated = update_template(
            self.db, tmpl.id, TemplateUpdate(title="Admin Updated Title"), self.admin_user
        )
        self.assertEqual(admin_updated.title, "Admin Updated Title")
        delete_template(self.db, tmpl.id, self.admin_user)

    # =========================================================================
    # 3. Campaign Schema Validation Tests
    # =========================================================================

    def test_campaign_schema_validation(self):
        """Test validation of channels, priorities, dates, and segment IDs."""
        now = datetime.now(timezone.utc)
        earlier = now - timedelta(days=2)

        # End date earlier than start date
        with self.assertRaises(ValueError) as ctx:
            CampaignCreate(
                name="Pulse Polio 2026",
                campaign_type="Awareness",
                channels=["Email"],
                start_date=now,
                end_date=earlier,
            )
        self.assertIn("End date must be greater than", str(ctx.exception))

        # Duplicate channel
        with self.assertRaises(ValueError) as ctx:
            CampaignCreate(
                name="Pulse Polio 2026",
                campaign_type="Awareness",
                channels=["Email", "email"],
            )
        self.assertIn("Duplicate channel", str(ctx.exception))

        # Invalid channel
        with self.assertRaises(ValueError) as ctx:
            CampaignCreate(
                name="Pulse Polio 2026",
                campaign_type="Awareness",
                channels=["CarrierPigeon"],
            )
        self.assertIn("Unsupported channel", str(ctx.exception))

        # Invalid segment ID (< 1)
        with self.assertRaises(ValueError) as ctx:
            CampaignCreate(
                name="Pulse Polio 2026",
                campaign_type="Awareness",
                channels=["Email"],
                segment_ids=[-5],
            )
        self.assertIn("Segment IDs must be positive", str(ctx.exception))

    # =========================================================================
    # 4. Campaign CRUD & Segment Associations
    # =========================================================================

    def test_campaign_creation_with_segments_and_template(self):
        """Test creating a campaign with multiple segments and a linked template."""
        tmpl = create_template(
            self.db,
            TemplateCreate(
                title="Dengue Alert Notice",
                category="Healthcare",
                body="Dear {name}, please take precautions in {city}.",
            ),
            self.manager_user,
        )

        create_data = CampaignCreate(
            name="Delhi Dengue Campaign",
            campaign_type="Awareness",
            objective="Prevent monsoon dengue outbreak",
            priority="High",
            channels=["Email", "WhatsApp"],
            template_id=tmpl.id,
            segment_ids=[self.seg_delhi.id, self.seg_hindi.id],
        )
        camp = create_campaign(self.db, create_data, self.manager_user)
        self.assertEqual(camp.name, "Delhi Dengue Campaign")
        self.assertEqual(camp.status, "Draft")
        self.assertEqual(camp.template_id, tmpl.id)
        self.assertEqual(len(camp.segments), 2)
        self.assertEqual(camp.creator_name, "Campaign Manager 1")

        # Non-existent segment ID raises 404
        bad_seg_data = CampaignCreate(
            name="Invalid Segment Campaign",
            campaign_type="Educational",
            channels=["SMS"],
            segment_ids=[99999],
        )
        with self.assertRaises(HTTPException) as ctx:
            create_campaign(self.db, bad_seg_data, self.manager_user)
        self.assertEqual(ctx.exception.status_code, 404)

        # Non-existent template ID raises 404
        bad_tmpl_data = CampaignCreate(
            name="Invalid Template Campaign",
            campaign_type="Educational",
            channels=["SMS"],
            template_id=99999,
        )
        with self.assertRaises(HTTPException) as ctx:
            create_campaign(self.db, bad_tmpl_data, self.manager_user)
        self.assertEqual(ctx.exception.status_code, 404)

    # =========================================================================
    # 5. Overlapping Segments Reach & Tri-State Consent Correctness
    # =========================================================================

    def test_overlapping_segments_deduplication_and_consent_counts(self):
        """
        Verify that overlapping segments count each audience member only once (DISTINCT)
        and confirmed opt-in consent is strictly distinguished from total reach.
        """
        camp_data = CampaignCreate(
            name="North India Outreach",
            campaign_type="Awareness",
            channels=["Email"],
            # seg_delhi (Aarav, Priya) and seg_hindi (Aarav, Priya) and seg_tamil (Karthik)
            segment_ids=[self.seg_delhi.id, self.seg_hindi.id, self.seg_tamil.id],
        )
        camp_resp = create_campaign(self.db, camp_data, self.manager_user)

        # In our seed data:
        # Delhi segment matches: Aarav (consent=True) and Priya (consent=None)
        # Hindi segment matches: Aarav and Priya
        # Tamil segment matches: Karthik (consent=True)
        # Total distinct matching audience: Aarav, Priya, Karthik = 3 (NOT 5 due to overlap)
        # Confirmed consent: Aarav and Karthik = 2 (Priya has consent=None, so NOT confirmed)
        self.assertEqual(camp_resp.total_target_audience, 3)
        self.assertEqual(camp_resp.confirmed_consent_audience, 2)

    # =========================================================================
    # 6. Campaign Lifecycle State Machine Tests
    # =========================================================================

    def test_campaign_lifecycle_transitions(self):
        """Test permitted lifecycle transitions and rejection of invalid status changes."""
        tmpl = create_template(
            self.db,
            TemplateCreate(
                title="Lifecycle Template",
                category="Civic Education",
                body="Civic message for {name}.",
            ),
            self.manager_user,
        )
        now = datetime.now(timezone.utc)
        camp = create_campaign(
            self.db,
            CampaignCreate(
                name="Lifecycle Test Campaign",
                campaign_type="Educational",
                channels=["Email"],
                template_id=tmpl.id,
                segment_ids=[self.seg_delhi.id],
                start_date=now + timedelta(days=1),
                end_date=now + timedelta(days=5),
            ),
            self.manager_user,
        )
        self.assertEqual(camp.status, "Draft")

        # 1. Draft -> In Review (Permitted)
        t1 = transition_campaign_status(self.db, camp.id, "In Review", self.manager_user)
        self.assertEqual(t1.status, "In Review")

        # 2. In Review -> Scheduled (Prohibited: must go through Approved first)
        with self.assertRaises(HTTPException) as ctx:
            transition_campaign_status(self.db, camp.id, "Scheduled", self.manager_user)
        self.assertEqual(ctx.exception.status_code, 400)

        # 3. In Review -> Approved (Permitted)
        t2 = transition_campaign_status(self.db, camp.id, "Approved", self.manager_user)
        self.assertEqual(t2.status, "Approved")

        # 4. Approved -> Scheduled (Permitted because start_date is set)
        t3 = transition_campaign_status(self.db, camp.id, "Scheduled", self.manager_user)
        self.assertEqual(t3.status, "Scheduled")

        # 5. Scheduled -> Draft (Permitted for cancellation/rescheduling)
        t4 = transition_campaign_status(self.db, camp.id, "Draft", self.manager_user)
        self.assertEqual(t4.status, "Draft")

        # 6. Draft -> Archived (Permitted terminal archiving)
        t5 = transition_campaign_status(self.db, camp.id, "Archived", self.manager_user)
        self.assertEqual(t5.status, "Archived")

        # 7. Archived -> Draft (Prohibited: Archived is terminal)
        with self.assertRaises(HTTPException) as ctx:
            transition_campaign_status(self.db, camp.id, "Draft", self.manager_user)
        self.assertEqual(ctx.exception.status_code, 400)

    def test_campaign_deletion_policy(self):
        """Only Draft or Archived campaigns may be deleted; Approved/Scheduled cannot be deleted."""
        tmpl = create_template(
            self.db,
            TemplateCreate(
                title="Deletion Policy Template",
                category="Public Governance",
                body="Governance message for {name}.",
            ),
            self.manager_user,
        )
        camp = create_campaign(
            self.db,
            CampaignCreate(
                name="Deletion Test Campaign",
                campaign_type="Educational",
                channels=["SMS"],
                template_id=tmpl.id,
                segment_ids=[self.seg_delhi.id],
            ),
            self.manager_user,
        )
        transition_campaign_status(self.db, camp.id, "In Review", self.manager_user)
        transition_campaign_status(self.db, camp.id, "Approved", self.manager_user)

        # Attempting to delete an Approved campaign -> 400 Bad Request
        with self.assertRaises(HTTPException) as ctx:
            delete_campaign(self.db, camp.id, self.manager_user)
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("Only Draft or Archived campaigns may be deleted", ctx.exception.detail)

        # Move back to Draft via state transition
        transition_campaign_status(self.db, camp.id, "Draft", self.manager_user)
        delete_campaign(self.db, camp.id, self.manager_user)

        # Verify deletion
        with self.assertRaises(HTTPException) as ctx:
            get_campaign_by_id(self.db, camp.id)
        self.assertEqual(ctx.exception.status_code, 404)

    def test_campaign_manager_ownership_restrictions(self):
        """Campaign Managers cannot update, delete, or transition status of another manager's campaign."""
        camp = create_campaign(
            self.db,
            CampaignCreate(
                name="Manager 1 Ownership Campaign",
                campaign_type="Awareness",
                channels=["Email"],
            ),
            self.manager_user,
        )

        # Manager 2 attempts update -> 403
        with self.assertRaises(HTTPException) as ctx:
            update_campaign(self.db, camp.id, CampaignUpdate(name="Manager 2 Tamper"), self.other_manager)
        self.assertEqual(ctx.exception.status_code, 403)

        # Manager 2 attempts transition -> 403
        with self.assertRaises(HTTPException) as ctx:
            transition_campaign_status(self.db, camp.id, "In Review", self.other_manager)
        self.assertEqual(ctx.exception.status_code, 403)

        # Manager 2 attempts delete -> 403
        with self.assertRaises(HTTPException) as ctx:
            delete_campaign(self.db, camp.id, self.other_manager)
        self.assertEqual(ctx.exception.status_code, 403)

        # Admin can update and delete -> Succeeds
        admin_updated = update_campaign(
            self.db, camp.id, CampaignUpdate(priority="Low"), self.admin_user
        )
        self.assertEqual(admin_updated.priority, "Low")
        delete_campaign(self.db, camp.id, self.admin_user)

    # =========================================================================
    # 7. Campaign Content Preview & Multi-Channel Formatting Tests
    # =========================================================================

    def test_campaign_preview_with_sample_recipient(self):
        """Test safe placeholder substitution and multi-channel metrics calculation."""
        tmpl = create_template(
            self.db,
            TemplateCreate(
                title="Monsoon Health Alert",
                category="Healthcare",
                body="Dear {name}, please visit {city} clinic or email {email} regarding health advisories.",
            ),
            self.manager_user,
        )
        camp = create_campaign(
            self.db,
            CampaignCreate(
                name="Monsoon Health Advisory",
                campaign_type="Emergency Alert",
                channels=["Email", "SMS", "WhatsApp", "Voice"],
                template_id=tmpl.id,
                segment_ids=[self.seg_delhi.id],
            ),
            self.manager_user,
        )

        preview = render_campaign_preview(self.db, camp.id, audience_member_id=self.aud_aarav.id)
        self.assertEqual(preview.campaign_id, camp.id)
        self.assertEqual(preview.sample_recipient["name"], "Aarav Sharma")
        self.assertIn("Dear Aarav Sharma", preview.rendered_content)
        self.assertIn("visit New Delhi clinic", preview.rendered_content)
        self.assertIn("aarav.sharma@example.gov.in", preview.rendered_content)

        # Channel specific checks
        channels = preview.channel_previews
        self.assertIn("Email", channels)
        self.assertIn("SMS", channels)
        self.assertIn("WhatsApp", channels)
        self.assertIn("Voice", channels)

        # Email has subject and HTML/Multipart format
        self.assertIn("Monsoon Health Advisory", channels["Email"].title_or_subject)
        self.assertEqual(channels["Email"].metrics["format"], "HTML / Multipart")

        # SMS has character count and segment count
        self.assertGreater(channels["SMS"].metrics["character_count"], 0)
        self.assertEqual(channels["SMS"].metrics["segment_count"], 1)

        # Voice has estimated duration
        self.assertGreater(channels["Voice"].metrics["estimated_duration_seconds"], 0)

    # =========================================================================
    # 8. Template Seeding Idempotency Tests
    # =========================================================================

    def test_seed_default_templates_idempotency(self):
        """Verify seeding creates exactly 6 templates and subsequent executions do not duplicate."""
        # Initial seed
        first_seed = seed_default_templates(self.db, creator_user_id=self.admin_user.id)
        self.assertEqual(len(first_seed), 6)

        # Check in DB
        count_stmt = select(func.count(Template.id))
        total_in_db = self.db.scalar(count_stmt)
        self.assertEqual(total_in_db, 6)

        # Modify one template's tags (user customizes template)
        dengue_tmpl = self.db.execute(
            select(Template).where(Template.title.ilike("%dengue%"))
        ).scalar_one()
        dengue_tmpl.tags = "customized,user_tag"
        self.db.commit()

        # Second seed run must NOT overwrite user's tag or create duplicate
        second_seed = seed_default_templates(self.db, creator_user_id=self.admin_user.id)
        self.assertEqual(len(second_seed), 6)

        self.db.refresh(dengue_tmpl)
        self.assertEqual(dengue_tmpl.tags, "customized,user_tag")
        total_after = self.db.scalar(count_stmt)
        self.assertEqual(total_after, 6)


if __name__ == "__main__":
    unittest.main()
