"""Comprehensive unit test suite for Task 7, Checkpoint 1: AI Provider & Backend Foundation."""

import unittest
import asyncio
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi import HTTPException

from app.db.base import Base
from app.db.seed import seed_default_roles
from app.models.user import User
from app.models.campaign import Campaign
from app.models.content_asset import ContentAsset
from app.core.security import get_password_hash
from app.services.ai.base import (
    ContentBrief,
    TranslationRequest,
    AIProviderError,
    AIProviderTimeoutError,
)
from app.services.ai.mock_provider import MockAIProvider, SUPPORTED_LANGUAGES
from app.services.ai.factory import get_ai_provider
from app.schemas.content_asset import (
    ContentGenerateRequest,
    ContentTranslateRequest,
    ContentAssetUpdate,
    ContentReviewStatusUpdate,
    ContentAttachRequest,
    ContentAssetResponse,
)
from app.services.content_service import (
    generate_content,
    translate_content,
    update_content_asset,
    update_review_status,
    attach_to_campaign_or_template,
    get_variants,
    list_content_assets,
    delete_content_asset,
)


class TestContentBackendFoundation(unittest.TestCase):
    """Test suite for AI Provider Abstraction, Content Schemas, and Service Layer."""

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
        self.comm_user = User(
            full_name="Comm Team Member",
            email="comm.staff@agency.gov.in",
            hashed_password=get_password_hash("CommPass123!"),
            role_id=self.comm_role.id,
            is_active=True,
        )
        self.db.add_all([self.admin_user, self.manager_user, self.comm_user])
        self.db.commit()

        # Seed sample campaign
        self.campaign = Campaign(
            name="Heatwave Alert 2026",
            campaign_type="Emergency Alert",
            objective="Alert citizens on extreme heat protocols",
            priority="High",
            status="Draft",
            channels=["Email", "SMS"],
            created_by=self.manager_user.id,
        )
        self.db.add(self.campaign)
        self.db.commit()

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)

    # -------------------------------------------------------------
    # 1. AI Provider Unit Tests
    # -------------------------------------------------------------

    def test_mock_provider_generation_across_channels(self):
        """Verify MockAIProvider generates channel-tailored awareness content."""
        provider = MockAIProvider()

        channels = ["Email", "SMS", "WhatsApp", "Voice"]
        for channel in channels:
            brief = ContentBrief(
                topic="Cyclone Preparedness",
                objective="Instruct coastal citizens to seek cyclone shelters",
                category="Disaster Preparedness",
                tone="urgent",
                channel=channel,
                source_language="en",
                facts="Helpline 1070 active. High wind warning.",
            )
            result = asyncio.run(provider.generate_content(brief))

            self.assertTrue(result.title)
            self.assertTrue(result.body)
            self.assertEqual(result.channel, channel)
            self.assertEqual(result.category, "Disaster Preparedness")
            self.assertEqual(result.provider_metadata.get("provider"), "mock")

            if channel == "SMS":
                # Ensure SMS contains alert and is within reasonable SMS bounds
                self.assertIn("ALERT", result.body)
                self.assertLess(len(result.body), 250)
            elif channel == "WhatsApp":
                self.assertIn("URGENT NOTICE", result.body)
            elif channel == "Voice":
                self.assertIn("announcement", result.body.lower())
            elif channel == "Email":
                self.assertIn("Dear {name}", result.body)

    def test_mock_provider_simulated_errors_and_timeouts(self):
        """Verify simulation hooks raise proper typed exceptions."""
        provider = MockAIProvider()

        # Timeout simulation
        timeout_brief = ContentBrief(
            topic="[SIMULATE_TIMEOUT] Dengue Alert",
            objective="Test timeout error handling",
            category="Healthcare",
            channel="SMS",
        )
        with self.assertRaises(AIProviderTimeoutError):
            asyncio.run(provider.generate_content(timeout_brief))

        # Upstream failure simulation
        error_brief = ContentBrief(
            topic="[SIMULATE_ERROR] Water Advisory",
            objective="Test general provider failure",
            category="Civic Services",
            channel="Email",
        )
        with self.assertRaises(AIProviderError):
            asyncio.run(provider.generate_content(error_brief))

    def test_mock_provider_multilingual_translation_and_placeholders(self):
        """Verify translation across Indian languages strictly preserves dynamic placeholders."""
        provider = MockAIProvider()

        for lang_code in ["ta", "hi", "te", "bn", "mr"]:
            req = TranslationRequest(
                source_text="Notice for {name} in {city}. Please consult {preferred_language} portal.",
                source_title="Advisory for {name}",
                source_cta="Contact {city} coordinator",
                source_language="en",
                target_language=lang_code,
            )
            res = asyncio.run(provider.translate_content(req))

            self.assertEqual(res.target_language, lang_code)
            self.assertIn(lang_code, SUPPORTED_LANGUAGES)

            # Strict placeholder verification
            full_text = f"{res.title} {res.body} {res.call_to_action}"
            self.assertIn("{name}", full_text)
            self.assertIn("{city}", full_text)
            self.assertIn("{preferred_language}", full_text)

    def test_translation_rejects_unsupported_language(self):
        """Verify requesting translation into unsupported language raises 400 error."""
        provider = MockAIProvider()
        req = TranslationRequest(
            source_text="Test notice",
            target_language="fr",  # French not supported in initial Indian languages set
        )
        with self.assertRaises(AIProviderError) as ctx:
            asyncio.run(provider.translate_content(req))
        self.assertEqual(ctx.exception.status_code, 400)

    # -------------------------------------------------------------
    # 2. Schema Validation & Computed Preview Fields
    # -------------------------------------------------------------

    def test_schema_channel_metrics_computation(self):
        """Verify ContentAssetResponse computed fields calculate accurate preview metrics."""
        response = ContentAssetResponse(
            id=1,
            title="Dengue Alert for {city}",
            body="Dear {name}, clear standing water around your home. Helpline: 104.",
            summary="Dengue advisory",
            call_to_action="Call 104 for help",
            category="Healthcare",
            tone="urgent",
            channel="SMS",
            source_language="en",
            target_language=None,
            operation_type="generation",
            review_status="Draft",
            created_by=self.manager_user.id,
            created_at=self.campaign.created_at,
            updated_at=self.campaign.created_at,
        )

        self.assertEqual(response.character_count, len(response.body))
        self.assertEqual(response.word_count, len(response.body.split()))
        self.assertEqual(response.sms_segment_count, 1)  # Length < 160
        self.assertGreaterEqual(response.voice_duration_seconds, 5)
        self.assertIn("{name}", response.detected_placeholders)
        self.assertIn("{city}", response.detected_placeholders)

    # -------------------------------------------------------------
    # 3. Content Service Layer Tests
    # -------------------------------------------------------------

    def test_generate_content_service_authoring_and_rbac(self):
        """Verify generate_content succeeds for Campaign Manager and is forbidden for Comm Team."""
        req = ContentGenerateRequest(
            topic="Seasonal Flu Vaccination",
            objective="Encourage senior citizens to receive flu immunization",
            audience_description="Citizens above age 60",
            category="Healthcare",
            tone="informative",
            channel="Email",
            source_language="en",
            facts="Free vaccines available at primary health centers.",
        )

        # Comm Team member cannot author
        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(generate_content(self.db, req, self.comm_user, provider_type="mock"))
        self.assertEqual(ctx.exception.status_code, 403)

        # Campaign Manager can author
        asset = asyncio.run(generate_content(self.db, req, self.manager_user, provider_type="mock"))
        self.assertIsNotNone(asset.id)
        self.assertEqual(asset.review_status, "Draft")  # Must be Draft, requiring human review
        self.assertEqual(asset.created_by, self.manager_user.id)
        self.assertEqual(asset.operation_type, "generation")

    def test_translate_content_service_creates_variant_and_preserves_parent(self):
        """Verify translation creates child variant linked via parent_id without altering source."""
        gen_req = ContentGenerateRequest(
            topic="Flood Warning",
            objective="Notify citizens regarding river basin flood risks",
            category="Disaster Preparedness",
            tone="urgent",
            channel="WhatsApp",
            source_language="en",
            facts="Emergency shelter open at Community Hall.",
        )
        source_asset = asyncio.run(generate_content(self.db, gen_req, self.manager_user, provider_type="mock"))
        original_body = source_asset.body

        trans_req = ContentTranslateRequest(target_language="ta")
        variant = asyncio.run(translate_content(self.db, source_asset.id, trans_req, self.manager_user, provider_type="mock"))

        # Source asset unchanged
        self.db.refresh(source_asset)
        self.assertEqual(source_asset.body, original_body)
        self.assertIsNone(source_asset.target_language)

        # Variant asset assertions
        self.assertNotEqual(variant.id, source_asset.id)
        self.assertEqual(variant.parent_id, source_asset.id)
        self.assertEqual(variant.target_language, "ta")
        self.assertEqual(variant.operation_type, "translation")
        self.assertEqual(variant.review_status, "Draft")  # Requires human review

        # Lineage retrieval
        variants = get_variants(self.db, source_asset.id, self.manager_user)
        self.assertEqual(len(variants), 2)
        self.assertEqual(variants[0].id, source_asset.id)
        self.assertEqual(variants[1].id, variant.id)

    def test_human_review_status_transition_and_audit(self):
        """Verify review status transitions and reviewer audit recording."""
        gen_req = ContentGenerateRequest(
            topic="National Nutrition Month",
            objective="Promote balanced nutrition for children",
            category="Healthcare",
            channel="SMS",
        )
        asset = asyncio.run(generate_content(self.db, gen_req, self.manager_user, provider_type="mock"))

        # Invalid transition: Draft directly to non-supported
        with self.assertRaises(HTTPException) as ctx:
            update_review_status(
                self.db,
                asset.id,
                ContentReviewStatusUpdate(review_status="Rejected"),
                self.admin_user,
            )
        self.assertEqual(ctx.exception.status_code, 400)

        # Valid transition: Draft -> In Review
        asset = update_review_status(
            self.db,
            asset.id,
            ContentReviewStatusUpdate(review_status="In Review", review_notes="Initial editorial pass"),
            self.admin_user,
        )
        self.assertEqual(asset.review_status, "In Review")
        self.assertEqual(asset.reviewed_by, self.admin_user.id)
        self.assertIsNotNone(asset.reviewed_at)

        # Valid transition: In Review -> Approved
        asset = update_review_status(
            self.db,
            asset.id,
            ContentReviewStatusUpdate(review_status="Approved", review_notes="Reviewed and confirmed facts"),
            self.admin_user,
        )
        self.assertEqual(asset.review_status, "Approved")

        # Human edit resets Approved back to In Review
        updated_asset = update_content_asset(
            self.db,
            asset.id,
            ContentAssetUpdate(body="Updated body with latest statistics."),
            self.admin_user,
        )
        self.assertEqual(updated_asset.review_status, "In Review")
        self.assertEqual(updated_asset.operation_type, "human_edit")

    def test_attach_content_to_campaign_and_template(self):
        """Verify associating content asset with existing campaign and saving as reusable template."""
        gen_req = ContentGenerateRequest(
            topic="Severe Heatwave Advisory",
            objective="Advise hydration and indoor safety",
            category="Emergency Alert",
            channel="Email",
        )
        asset = asyncio.run(generate_content(self.db, gen_req, self.manager_user, provider_type="mock"))

        attach_req = ContentAttachRequest(
            campaign_id=self.campaign.id,
            save_as_template=True,
            template_name="Heatwave Advisory Template",
            template_category="Healthcare",
        )

        result = attach_to_campaign_or_template(self.db, asset.id, attach_req, self.manager_user)

        self.assertEqual(result["attached_campaign_id"], self.campaign.id)
        self.assertIn("saved_template_id", result)

        # Campaign template link is updated, but status remains Draft
        self.db.refresh(self.campaign)
        self.assertEqual(self.campaign.template_id, result["saved_template_id"])
        self.assertEqual(self.campaign.template.body, asset.body)
        self.assertEqual(self.campaign.status, "Draft")  # No bypass of campaign lifecycle


if __name__ == "__main__":
    unittest.main()
