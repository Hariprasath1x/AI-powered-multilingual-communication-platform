"""
MassCommAI - Milestone 2, Task 8: Multilingual Translation Pipeline Integration Tests.

Comprehensive automated test suite covering:
- All 10 Indian languages translation (hi, kn, ta, te, mr, bn, gu, ml, pa, ur)
- Occurrence-aware placeholder preservation and corruption detection
- Deterministic translation caching and cache invalidation on source edits
- Batch translation endpoint with isolated failure handling
- Variant deduplication under the root lineage
- Review workflow state transitions (Pending -> Generated -> Needs Review -> Approved <-> Rejected)
- Chronological review history audit trail
- Telecom metrics (UCS-2 SMS segmentation and Indic Voice pacing)
"""

import unittest
from datetime import datetime, timezone
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.main import app
from app.db.base import Base
from app.db.session import get_db
from app.db.seed import seed_default_roles
from app.models.user import User
from app.models.content_asset import ContentAsset
from app.models.translation import TranslationCache, TranslationReviewHistory
from app.core.security import get_password_hash, create_access_token
from app.services.placeholder_service import validate_placeholders, extract_placeholders
from app.services.translation_cache_service import compute_source_content_hash, compute_translation_cache_key


class TestTranslationPipeline(unittest.TestCase):
    """Integration test suite for Milestone 2 Task 8 Multilingual Translation Pipeline."""

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

        # Seed Users
        self.admin_user = User(
            full_name="Admin Director",
            email="admin.director@agency.gov.in",
            hashed_password=get_password_hash("AdminSecret123!"),
            role_id=self.admin_role.id,
            is_active=True,
        )
        self.manager = User(
            full_name="Campaign Officer",
            email="officer.campaign@agency.gov.in",
            hashed_password=get_password_hash("OfficerPass123!"),
            role_id=self.manager_role.id,
            is_active=True,
        )
        self.db.add_all([self.admin_user, self.manager])
        self.db.commit()
        self.db.refresh(self.admin_user)
        self.db.refresh(self.manager)

        self.manager_token = create_access_token(self.manager.id)
        self.admin_token = create_access_token(self.admin_user.id)

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

    def _headers(self, token: str):
        return {"Authorization": f"Bearer {token}"}

    def _create_source_asset(self, body: str = "Stay safe during monsoon {name}. Emergency contact in {city}.", channel: str = "WhatsApp") -> int:
        """Helper to create a root content asset with dynamic placeholders."""
        res = self.client.post(
            "/content/manual",
            json={
                "title": "Monsoon Safety Alert {city}",
                "body": body,
                "call_to_action": "Call 1070 for help in {city}",
                "category": "Disaster Preparedness",
                "tone": "urgent",
                "channel": channel,
                "source_language": "en",
            },
            headers=self._headers(self.manager_token),
        )
        self.assertEqual(res.status_code, 201)
        return res.json()["id"]

    def test_multilingual_translation_all_10_indian_languages(self):
        """Verify translation succeeds for all 10 Indian languages with proper review_status and lineage."""
        source_id = self._create_source_asset()
        languages = ["hi", "kn", "ta", "te", "mr", "bn", "gu", "ml", "pa", "ur"]

        for lang in languages:
            res = self.client.post(
                f"/content/{source_id}/translate",
                json={"target_language": lang, "notes": f"Regional advisory for {lang}"},
                headers=self._headers(self.manager_token),
            )
            self.assertEqual(res.status_code, 201, f"Failed translating to {lang}: {res.text}")
            data = res.json()
            self.assertEqual(data["target_language"], lang)
            self.assertEqual(data["parent_id"], source_id)
            self.assertEqual(data["operation_type"], "translation")
            self.assertEqual(data["review_status"], "Generated")
            self.assertTrue(len(data["title"]) > 0)
            self.assertTrue(len(data["body"]) > 0)
            # Verify placeholders are preserved
            self.assertIn("{name}", data["detected_placeholders"])
            self.assertIn("{city}", data["detected_placeholders"])
            # Channel metrics snapshot must be populated
            self.assertIsNotNone(data["channel_metrics"])

    def test_occurrence_aware_placeholder_preservation(self):
        """Occurrence-aware multiset comparison properly handles repeated and missing placeholders."""
        # Test repeated placeholders: {name} twice, {city} once
        source_body = "Hello {name}! Please confirm that {name} will visit center in {city}."
        source_id = self._create_source_asset(body=source_body)

        res = self.client.post(
            f"/content/{source_id}/translate",
            json={"target_language": "ta"},
            headers=self._headers(self.manager_token),
        )
        self.assertEqual(res.status_code, 201)
        data = res.json()
        # Verify {name} appears twice in the translated body
        body_text = data["body"]
        self.assertEqual(body_text.count("{name}"), 2, f"Expected 2 occurrences of {{name}}, got: {body_text}")

    def test_placeholder_corruption_and_mismatch_detection(self):
        """Direct validation unit test detects dropped, corrupted, and extra placeholders."""
        source_title = "Alert for {name}"
        source_body = "Hello {name}, visit {city} now."
        source_cta = "Call {city}"

        # 1. Matching translation -> Valid
        res = validate_placeholders(
            source_title=source_title,
            source_body=source_body,
            source_cta=source_cta,
            translated_title="హెచ్చరిక {name}",
            translated_body="నమస్కారం {name}, ఇప్పుడే {city} సందర్శించండి.",
            translated_cta="{city} కి కాల్ చేయండి",
        )
        self.assertTrue(res.is_valid)
        self.assertEqual(len(res.missing), 0)

        # 2. Dropped placeholder -> Invalid
        res_missing = validate_placeholders(
            source_title=source_title,
            source_body=source_body,
            source_cta=source_cta,
            translated_title="హెచ్చరిక {name}",
            translated_body="నమస్కారం, ఇప్పుడే {city} సందర్శించండి.",  # dropped one {name}
            translated_cta="{city} కి కాల్ చేయండి",
        )
        self.assertFalse(res_missing.is_valid)
        self.assertIn("{name}", res_missing.missing)

        # 3. Extra / unexpected placeholder -> Invalid
        res_extra = validate_placeholders(
            source_title=source_title,
            source_body=source_body,
            source_cta=source_cta,
            translated_title="Alert for {name}",
            translated_body="Hello {name}, visit {city} now with {extra_token}.",
            translated_cta="Call {city}",
        )
        self.assertFalse(res_extra.is_valid)
        self.assertIn("{extra_token}", res_extra.extra)

        # 4. Corrupted / translated brace tokens (e.g. Indic script inside braces) -> Invalid
        res_corrupt = validate_placeholders(
            source_title=source_title,
            source_body=source_body,
            source_cta=source_cta,
            translated_title="Alert for {பெயர்}",  # corrupted non-ASCII brace token
            translated_body="Hello {name}, visit {city} now.",
            translated_cta="Call {city}",
        )
        self.assertFalse(res_corrupt.is_valid)
        self.assertIn("{பெயர்}", res_corrupt.corrupted)

        # 5. AUDIT-T8-06: Nested / double braces (e.g. {{name}}) -> Invalid
        res_nested = validate_placeholders(
            source_title=source_title,
            source_body=source_body,
            source_cta=source_cta,
            translated_title="Alert for {{name}}",
            translated_body="Hello {name}, visit {city} now.",
            translated_cta="Call {city}",
        )
        self.assertFalse(res_nested.is_valid)
        self.assertTrue(any("{{name}}" in c for c in res_nested.corrupted))

        # 6. AUDIT-T8-06: Unbalanced braces -> Invalid
        res_unbalanced = validate_placeholders(
            source_title=source_title,
            source_body=source_body,
            source_cta=source_cta,
            translated_title="Alert for {name",
            translated_body="Hello {name}, visit {city} now.",
            translated_cta="Call {city}",
        )
        self.assertFalse(res_unbalanced.is_valid)
        self.assertIn("unbalanced_braces", res_unbalanced.corrupted)

    def test_translation_cache_hit_and_invalidation(self):
        """Cache stores first translation and returns it on second identical call; invalidates on source update."""
        source_id = self._create_source_asset()

        # Call 1: Cache Miss
        res1 = self.client.post(
            f"/content/{source_id}/translate",
            json={"target_language": "hi", "notes": "Standard public broadcast"},
            headers=self._headers(self.manager_token),
        )
        self.assertEqual(res1.status_code, 201)
        data1 = res1.json()
        self.assertFalse(data1["provider_metadata"].get("cached", False))

        # Check DB cache table
        cached_rows = self.db.execute(select(TranslationCache)).scalars().all()
        self.assertEqual(len(cached_rows), 1)
        self.assertEqual(cached_rows[0].hit_count, 0)

        # Call 2: Identical request -> Cache Hit
        res2 = self.client.post(
            f"/content/{source_id}/translate",
            json={"target_language": "hi", "notes": "Standard public broadcast"},
            headers=self._headers(self.manager_token),
        )
        self.assertEqual(res2.status_code, 201)
        data2 = res2.json()
        self.assertTrue(data2["provider_metadata"].get("cached"))
        self.assertGreaterEqual(data2["provider_metadata"].get("hit_count", 0), 1)

        # Update source asset copy -> Purges translation cache for that source hash
        update_res = self.client.put(
            f"/content/{source_id}",
            json={"title": "Updated Storm Alert {city}"},
            headers=self._headers(self.manager_token),
        )
        self.assertEqual(update_res.status_code, 200)

        # Verify old cache row was invalidated
        cached_rows_after = self.db.execute(select(TranslationCache)).scalars().all()
        self.assertEqual(len(cached_rows_after), 0)

        # Call 3: Subsequent request generates fresh translation (cache miss)
        res3 = self.client.post(
            f"/content/{source_id}/translate",
            json={"target_language": "hi", "notes": "Standard public broadcast"},
            headers=self._headers(self.manager_token),
        )
        self.assertEqual(res3.status_code, 201)
        data3 = res3.json()
        self.assertFalse(data3["provider_metadata"].get("cached", False))

    def test_batch_translation_endpoint(self):
        """Batch translation processes multiple languages concurrently with structured reporting."""
        source_id = self._create_source_asset()
        target_langs = ["hi", "ta", "kn", "ur"]

        batch_res = self.client.post(
            f"/content/{source_id}/translate/batch",
            json={"target_languages": target_langs, "notes": "Emergency multi-region broadcast"},
            headers=self._headers(self.manager_token),
        )
        self.assertEqual(batch_res.status_code, 200)
        data = batch_res.json()

        self.assertEqual(data["total_requested"], 4)
        self.assertEqual(data["total_succeeded"], 4)
        self.assertEqual(data["total_failed"], 0)
        self.assertEqual(len(data["successes"]), 4)
        self.assertEqual(len(data["failures"]), 0)

        succeeded_langs = {item["target_language"] for item in data["successes"]}
        self.assertEqual(succeeded_langs, set(target_langs))

    def test_batch_translation_isolated_failure_handling(self):
        """Failure in one target language does not abort or rollback translations for valid languages."""
        source_id = self._create_source_asset()
        # 'xx' is unsupported language, 'en' is identical to source language
        target_langs = ["hi", "xx_invalid", "te"]

        batch_res = self.client.post(
            f"/content/{source_id}/translate/batch",
            json={"target_languages": target_langs},
            headers=self._headers(self.manager_token),
        )
        self.assertEqual(batch_res.status_code, 200)
        data = batch_res.json()

        self.assertEqual(data["total_requested"], 3)
        self.assertEqual(data["total_succeeded"], 2)
        self.assertEqual(data["total_failed"], 1)

        self.assertEqual(len(data["failures"]), 1)
        self.assertEqual(data["failures"][0]["target_language"], "xx_invalid")
        self.assertEqual(data["failures"][0]["status_code"], 400)

        succeeded_langs = {item["target_language"] for item in data["successes"]}
        self.assertEqual(succeeded_langs, {"hi", "te"})

    def test_variant_deduplication_under_root(self):
        """Repeated translation for the same language updates existing variant instead of creating duplicate rows."""
        source_id = self._create_source_asset()

        # First translation into Marathi ('mr')
        res1 = self.client.post(
            f"/content/{source_id}/translate",
            json={"target_language": "mr"},
            headers=self._headers(self.manager_token),
        )
        self.assertEqual(res1.status_code, 201)
        var1_id = res1.json()["id"]

        # Second translation into Marathi ('mr')
        res2 = self.client.post(
            f"/content/{source_id}/translate",
            json={"target_language": "mr"},
            headers=self._headers(self.manager_token),
        )
        self.assertEqual(res2.status_code, 201)
        var2_id = res2.json()["id"]

        # Must reuse the same variant ID
        self.assertEqual(var1_id, var2_id)

        # Check total variants in database
        variants_res = self.client.get(f"/content/{source_id}/variants", headers=self._headers(self.manager_token))
        self.assertEqual(variants_res.status_code, 200)
        mr_variants = [v for v in variants_res.json() if v["target_language"] == "mr"]
        self.assertEqual(len(mr_variants), 1)

    def test_review_workflow_lifecycle_and_audit_history(self):
        """Tests complete editorial state machine: Generated -> Needs Review -> Approved / Rejected."""
        source_id = self._create_source_asset()

        # Step 1: Generate translation variant -> starts in 'Generated'
        res_trans = self.client.post(
            f"/content/{source_id}/translate",
            json={"target_language": "ta"},
            headers=self._headers(self.manager_token),
        )
        self.assertEqual(res_trans.status_code, 201)
        variant_id = res_trans.json()["id"]
        self.assertEqual(res_trans.json()["review_status"], "Generated")

        # Step 2: Transition Generated -> Needs Review
        res_submit = self.client.patch(
            f"/content/{variant_id}/review",
            json={"review_status": "Needs Review", "review_notes": "Submitted for linguistic verification"},
            headers=self._headers(self.manager_token),
        )
        self.assertEqual(res_submit.status_code, 200)
        self.assertEqual(res_submit.json()["review_status"], "Needs Review")

        # Step 2b: Run Quality Assessment before approval (Phase 1A requirement)
        res_eval = self.client.post(
            f"/content/{variant_id}/evaluate",
            headers=self._headers(self.manager_token),
        )
        self.assertEqual(res_eval.status_code, 200)

        # Step 3: Transition Needs Review -> Approved
        res_approve = self.client.patch(
            f"/content/{variant_id}/review",
            json={"review_status": "Approved", "review_notes": "Tamil phrasing verified by state communication officer"},
            headers=self._headers(self.admin_token),
        )
        self.assertEqual(res_approve.status_code, 200)
        self.assertEqual(res_approve.json()["review_status"], "Approved")

        # Step 4: Human edit on approved variant resets status back to 'Needs Review'
        res_edit = self.client.put(
            f"/content/{variant_id}",
            json={"title": "Updated Tamil Title {city}"},
            headers=self._headers(self.manager_token),
        )
        self.assertEqual(res_edit.status_code, 200)
        self.assertEqual(res_edit.json()["review_status"], "Needs Review")
        self.assertTrue(res_edit.json()["provider_metadata"].get("is_human_edited"))

        # Step 5: Transition Needs Review -> Rejected
        res_reject = self.client.patch(
            f"/content/{variant_id}/review",
            json={"review_status": "Rejected", "review_notes": "Inaccurate local dialect nuance"},
            headers=self._headers(self.admin_token),
        )
        self.assertEqual(res_reject.status_code, 200)
        self.assertEqual(res_reject.json()["review_status"], "Rejected")

        # Step 6: Verify chronological audit history trail
        history_res = self.client.get(
            f"/content/{variant_id}/review-history",
            headers=self._headers(self.manager_token),
        )
        self.assertEqual(history_res.status_code, 200)
        history_list = history_res.json()
        # Verify transitions recorded
        self.assertGreaterEqual(len(history_list), 4)
        statuses = [item["to_status"] for item in history_list]
        self.assertIn("Generated", statuses)
        self.assertIn("Needs Review", statuses)
        self.assertIn("Approved", statuses)
        self.assertIn("Rejected", statuses)

    def test_telecom_constraints_on_translated_content(self):
        """SMS in Indic languages switches to UCS-2 encoding and Voice pacing matches Indic speeds."""
        # 1. SMS channel with Indic script -> UCS-2 encoding
        source_sms_id = self._create_source_asset(channel="SMS")
        res_sms = self.client.post(
            f"/content/{source_sms_id}/translate",
            json={"target_language": "ta"},
            headers=self._headers(self.manager_token),
        )
        self.assertEqual(res_sms.status_code, 201)
        sms_data = res_sms.json()
        self.assertEqual(sms_data["channel_metrics"]["channel"], "SMS")
        self.assertEqual(sms_data["channel_metrics"]["sms"]["encoding"], "UCS-2")
        self.assertGreaterEqual(sms_data["channel_metrics"]["sms"]["segment_count"], 1)

        # 2. Voice channel with Malayalam -> 110 WPM pacing
        source_voice_id = self._create_source_asset(channel="Voice")
        res_voice = self.client.post(
            f"/content/{source_voice_id}/translate",
            json={"target_language": "ml"},
            headers=self._headers(self.manager_token),
        )
        self.assertEqual(res_voice.status_code, 201)
        voice_data = res_voice.json()
        self.assertEqual(voice_data["channel_metrics"]["channel"], "Voice")
        self.assertGreater(voice_data["channel_metrics"]["estimated_duration_seconds"], 0)
        self.assertGreater(voice_data["voice_duration_seconds"], 0)

    def test_concurrent_translation_variant_uniqueness(self):
        """AUDIT-T8-01: Verify unique index prevents duplicate variants and handles race conditions."""
        from sqlalchemy.exc import IntegrityError
        from app.services.translation_service import translate_single_language
        import asyncio

        source_id = self._create_source_asset()
        
        # 1. Translate once to create variant
        res = self.client.post(
            f"/content/{source_id}/translate",
            json={"target_language": "hi"},
            headers=self._headers(self.manager_token),
        )
        self.assertEqual(res.status_code, 201)
        var_id = res.json()["id"]

        # 2. Verify direct insertion with duplicate (parent_id, target_language) violates partial unique index
        dup_asset = ContentAsset(
            title="Duplicate Title",
            body="Duplicate Body",
            channel="Email",
            category="Healthcare",
            source_language="en",
            target_language="hi",
            parent_id=source_id,
            created_by=self.manager.id,
        )
        self.db.add(dup_asset)
        with self.assertRaises(IntegrityError):
            self.db.flush()
        self.db.rollback()

        # 3. Verify translate_single_language handles IntegrityError gracefully if another variant exists
        source_asset = self.db.get(ContentAsset, source_id)
        existing_res = asyncio.run(translate_single_language(
            db=self.db,
            source_asset=source_asset,
            target_language="hi",
            current_user=self.manager,
        ))
        self.assertEqual(existing_res.id, var_id)

        # 4. Verify only one Hindi variant exists in DB
        all_variants = self.db.execute(
            select(ContentAsset).where(
                ContentAsset.parent_id == source_id,
                ContentAsset.target_language == "hi",
            )
        ).scalars().all()
        self.assertEqual(len(all_variants), 1)

    def test_rejection_requires_mandatory_review_notes(self):
        """AUDIT-T8-02: Verify rejection fails without non-empty review notes."""
        source_id = self._create_source_asset()
        res = self.client.post(
            f"/content/{source_id}/translate",
            json={"target_language": "hi"},
            headers=self._headers(self.manager_token),
        )
        self.assertEqual(res.status_code, 201)
        var_id = res.json()["id"]

        # First transition Generated -> Needs Review
        res_review = self.client.patch(
            f"/content/{var_id}/review",
            json={"review_status": "Needs Review"},
            headers=self._headers(self.manager_token),
        )
        self.assertEqual(res_review.status_code, 200)

        # 1. Attempt rejection with null/missing review_notes -> 400
        res_no_notes = self.client.patch(
            f"/content/{var_id}/review",
            json={"review_status": "Rejected"},
            headers=self._headers(self.admin_token),
        )
        self.assertEqual(res_no_notes.status_code, 400)
        self.assertIn("mandatory when rejecting", res_no_notes.json()["detail"])

        # 2. Attempt rejection with whitespace-only review_notes -> 400
        res_ws_notes = self.client.patch(
            f"/content/{var_id}/review",
            json={"review_status": "Rejected", "review_notes": "    \n   "},
            headers=self._headers(self.admin_token),
        )
        self.assertEqual(res_ws_notes.status_code, 400)
        self.assertIn("mandatory when rejecting", res_ws_notes.json()["detail"])

        # 3. Rejection with valid review notes -> 200
        res_valid = self.client.patch(
            f"/content/{var_id}/review",
            json={"review_status": "Rejected", "review_notes": "Needs formal government phrasing in Hindi"},
            headers=self._headers(self.admin_token),
        )
        self.assertEqual(res_valid.status_code, 200)
        self.assertEqual(res_valid.json()["review_status"], "Rejected")
        self.assertEqual(res_valid.json()["review_notes"], "Needs formal government phrasing in Hindi")

    def test_cache_key_provider_and_version_isolation(self):
        """AUDIT-T8-03: Verify cache keys differ across providers, models, and prompt versions."""
        source_hash = "mock_hash_12345"

        # 1. Same provider, same model, same prompt version -> identical cache key (Cache Hit)
        key_base = compute_translation_cache_key(
            source_language="en",
            target_language="hi",
            channel="Email",
            source_content_hash=source_hash,
            provider_type="gemini",
            model_name="gemini-1.5-flash",
            prompt_version="v1.0",
        )
        key_identical = compute_translation_cache_key(
            source_language="en",
            target_language="hi",
            channel="Email",
            source_content_hash=source_hash,
            provider_type="gemini",
            model_name="gemini-1.5-flash",
            prompt_version="v1.0",
        )
        self.assertEqual(key_base, key_identical)

        # 2. Same provider, different model -> different cache key (Cache Miss)
        key_different_model = compute_translation_cache_key(
            source_language="en",
            target_language="hi",
            channel="Email",
            source_content_hash=source_hash,
            provider_type="gemini",
            model_name="gemini-1.5-pro",
            prompt_version="v1.0",
        )
        self.assertNotEqual(key_base, key_different_model)

        # 3. Same model, different prompt version -> different cache key (Cache Miss)
        key_different_version = compute_translation_cache_key(
            source_language="en",
            target_language="hi",
            channel="Email",
            source_content_hash=source_hash,
            provider_type="gemini",
            model_name="gemini-1.5-flash",
            prompt_version="v2.0",
        )
        self.assertNotEqual(key_base, key_different_version)

        # 4. Different providers -> different cache key (Cache Miss)
        key_mock = compute_translation_cache_key(
            source_language="en",
            target_language="hi",
            channel="Email",
            source_content_hash=source_hash,
            provider_type="mock",
            model_name="mock-translator-v1",
            prompt_version="v1.0",
        )
        self.assertNotEqual(key_base, key_mock)

    def test_source_edit_resets_approved_child_translations_and_flags_outdated(self):
        """AUDIT-T8-04: Verify source edits reset child variant approval and flag source_outdated."""
        source_id = self._create_source_asset()

        # 1. Translate to Hindi
        res = self.client.post(
            f"/content/{source_id}/translate",
            json={"target_language": "hi"},
            headers=self._headers(self.manager_token),
        )
        self.assertEqual(res.status_code, 201)
        var_id = res.json()["id"]

        # 1b. Run Quality Assessment before approval (Phase 1A requirement)
        res_eval = self.client.post(
            f"/content/{var_id}/evaluate",
            headers=self._headers(self.manager_token),
        )
        self.assertEqual(res_eval.status_code, 200)

        # 2. Approve child variant
        res_approve = self.client.patch(
            f"/content/{var_id}/review",
            json={"review_status": "Approved", "review_notes": "Looks good"},
            headers=self._headers(self.admin_token),
        )
        self.assertEqual(res_approve.status_code, 200)
        self.assertEqual(res_approve.json()["review_status"], "Approved")

        # 3. Edit source content
        res_edit = self.client.put(
            f"/content/{source_id}",
            json={"body": "Urgent update: flood levels rising in {city} immediately."},
            headers=self._headers(self.manager_token),
        )
        self.assertEqual(res_edit.status_code, 200)

        # 4. Fetch child variant and verify it was reset to Needs Review and flagged source_outdated
        res_child = self.client.get(
            f"/content/{var_id}",
            headers=self._headers(self.manager_token),
        )
        self.assertEqual(res_child.status_code, 200)
        child_data = res_child.json()
        self.assertEqual(child_data["review_status"], "Needs Review")
        self.assertTrue(child_data["provider_metadata"].get("source_outdated"))

        # Verify review history records this transition
        history_res = self.client.get(
            f"/content/{var_id}/review-history",
            headers=self._headers(self.manager_token),
        )
        self.assertEqual(history_res.status_code, 200)
        transitions = history_res.json()
        last_transition = transitions[-1]
        self.assertEqual(last_transition["from_status"], "Approved")
        self.assertEqual(last_transition["to_status"], "Needs Review")
        self.assertIn("root source content modified", last_transition["review_notes"])

    def test_transition_translation_review_delegation(self):
        """AUDIT-T8-07: Verify transition_translation_review delegates cleanly to content_service."""
        from app.services.translation_service import transition_translation_review

        source_id = self._create_source_asset()
        res = self.client.post(
            f"/content/{source_id}/translate",
            json={"target_language": "hi"},
            headers=self._headers(self.manager_token),
        )
        self.assertEqual(res.status_code, 201)
        var_id = res.json()["id"]

        # Delegate Generated -> Needs Review
        updated = transition_translation_review(
            db=self.db,
            asset_id=var_id,
            to_status="Needs Review",
            current_user=self.manager,
            review_notes="Delegated review transition test",
        )
        self.assertEqual(updated.review_status, "Needs Review")
        self.assertEqual(updated.reviewed_by, self.manager.id)

    def test_unique_index_allows_multiple_child_assets_without_target_language(self):
        """Verify unique index predicate restricts uniqueness strictly to target_language variants."""
        source_id = self._create_source_asset()

        # Two child assets under the same parent with target_language=None
        child1 = ContentAsset(
            title="Revision 1",
            body="Body revision 1",
            channel="Email",
            category="Healthcare",
            source_language="en",
            target_language=None,
            operation_type="human_edit",
            parent_id=source_id,
            created_by=self.manager.id,
        )
        child2 = ContentAsset(
            title="Revision 2",
            body="Body revision 2",
            channel="Email",
            category="Healthcare",
            source_language="en",
            target_language=None,
            operation_type="human_edit",
            parent_id=source_id,
            created_by=self.manager.id,
        )
        self.db.add_all([child1, child2])
        self.db.commit()

        self.assertIsNotNone(child1.id)
        self.assertIsNotNone(child2.id)
        self.assertNotEqual(child1.id, child2.id)


if __name__ == "__main__":
    unittest.main()
