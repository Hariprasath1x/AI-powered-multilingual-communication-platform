"""Test suite for Sentiment-Aware Tone Analysis & Optimization (Milestone 2, Task 10)."""

import unittest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.main import app
from app.db.base import Base
from app.db.session import get_db
from app.db.seed import seed_default_roles
from app.models.content_asset import ContentAsset
from app.models.user import User
from app.models.campaign import Campaign
from app.core.security import get_password_hash, create_access_token
from app.schemas.tone import ToneClassification
from app.services.tone_service import (
    calculate_sentiment_polarity,
    classify_five_way_tone,
    calculate_readability,
    calculate_clarity_score,
    detect_formatting_anomalies,
    verify_and_repair_factual_anchors,
    compute_word_diff,
)


class TestToneAlgorithmsUnit(unittest.TestCase):
    """Unit tests for deterministic sentiment, tone classification, and diff algorithms."""

    def test_five_way_tone_classification_all_categories(self):
        # 1. Urgent
        t_urg, _ = classify_five_way_tone("URGENT: Take immediate action now! Evacuate without delay.")
        self.assertEqual(t_urg, ToneClassification.URGENT.value)

        # 2. Friendly
        t_fr, _ = classify_five_way_tone("Dear neighbors, welcome to our community event! We are delighted to support you.")
        self.assertEqual(t_fr, ToneClassification.FRIENDLY.value)

        # 3. Formal
        t_for, _ = classify_five_way_tone("Official Notice: In accordance with statutory regulations, citizens are hereby notified.")
        self.assertEqual(t_for, ToneClassification.FORMAL.value)

        # 4. Harsh
        t_harsh, _ = classify_five_way_tone("Failure to comply will cause catastrophic consequences and deadly panic for all!")
        self.assertEqual(t_harsh, ToneClassification.HARSH.value)

        # 5. Neutral
        t_neut, _ = classify_five_way_tone("The public library operates from 9 AM to 5 PM on weekdays.")
        self.assertEqual(t_neut, ToneClassification.NEUTRAL.value)

    def test_sentiment_polarity_positive_negative_neutral(self):
        # Positive
        pos_score = calculate_sentiment_polarity("Our community is safe, healthy, and resilient thanks to helpful citizen cooperation.")
        self.assertGreater(pos_score, 0.3)

        # Negative / Alarmist
        neg_score = calculate_sentiment_polarity("Catastrophic devastation and deadly panic will destroy our fragile community.")
        self.assertLess(neg_score, -0.5)

        # Neutral
        neut_score = calculate_sentiment_polarity("The municipal office is located at 123 Civil Lines.")
        self.assertGreaterEqual(neut_score, -0.15)
        self.assertLessEqual(neut_score, 0.15)

        # Boundaries
        self.assertGreaterEqual(pos_score, -1.0)
        self.assertLessEqual(pos_score, 1.0)
        self.assertGreaterEqual(neg_score, -1.0)
        self.assertLessEqual(neg_score, 1.0)

    def test_readability_and_clarity_calculation(self):
        # High readability (simple sentences)
        fre_easy, label_easy = calculate_readability("Stay calm. Wash hands. Drink clean water. Call us for help.")
        self.assertGreaterEqual(fre_easy, 70.0)

        # Difficult readability (long compound clauses)
        fre_hard, label_hard = calculate_readability(
            "Pursuant to the administrative prerogatives establishing jurisdictional oversight concerning prophylactic measures, "
            "all constituent residents are obligated to systematically execute compliance verification procedures notwithstanding antecedent exemptions."
        )
        self.assertLess(fre_hard, 50.0)

        # Clarity
        clarity_high = calculate_clarity_score("Wash your hands with soap. It keeps everyone healthy.")
        self.assertGreaterEqual(clarity_high, 90.0)

    def test_formatting_anomalies_detection(self):
        anomalies = detect_formatting_anomalies("ATTENTION CITIZENS!! DO NOT GO OUTSIDE NOW???")
        self.assertGreaterEqual(len(anomalies), 2)
        self.assertTrue(any("exclamation" in a.lower() for a in anomalies))
        self.assertTrue(any("all-caps" in a.lower() or "uppercase" in a.lower() for a in anomalies))

    def test_factual_anchor_preservation_and_repair(self):
        original = "Please contact helpline 104 or 108 by 25/12/2026. Visit https://state.gov.in. Dear {name}."
        # Simulate rewrite dropping helpline and date
        bad_rewrite = "Please be informed about the civic drive. Visit https://state.gov.in. Dear {name}."

        repaired, result = verify_and_repair_factual_anchors(original, bad_rewrite)
        self.assertEqual(result.status, "repaired")
        self.assertTrue("104" in repaired or "108" in repaired)
        self.assertIn("25/12/2026", repaired)
        self.assertIn("{name}", repaired)

    def test_word_level_diff_computation(self):
        orig = "Take immediate precautions against flood"
        imp = "Take proactive precautions against flood safely"
        diff = compute_word_diff(orig, imp)
        self.assertGreaterEqual(diff.added_words_count, 1)
        self.assertGreaterEqual(diff.deleted_words_count, 1)
        self.assertGreater(len(diff.chunks), 0)


class TestToneAPIsIntegration(unittest.TestCase):
    """Integration test suite covering POST /content/{id}/tone/analyze and POST /content/{id}/tone/improve."""

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
        Base.metadata.create_all(bind=cls.test_engine)

    @classmethod
    def tearDownClass(cls):
        Base.metadata.drop_all(bind=cls.test_engine)

    def setUp(self):
        self.db = self.TestingSessionLocal()
        # Clean all tables before test run
        for table in reversed(Base.metadata.sorted_tables):
            self.db.execute(table.delete())
        self.db.commit()

        roles = seed_default_roles(self.db)
        self.admin_role = roles["Admin"]
        self.manager_role = roles["Campaign Manager"]
        self.comm_role = roles["Communication Team"]

        self.manager_user = User(
            full_name="Manager Health",
            email="manager.health@state.gov.in",
            hashed_password=get_password_hash("Secret123!"),
            role_id=self.manager_role.id,
            is_active=True,
            organization="Health Department",
        )
        self.other_dept_user = User(
            full_name="Other Dept Officer",
            email="other.dept@state.gov.in",
            hashed_password=get_password_hash("Secret123!"),
            role_id=self.manager_role.id,
            is_active=True,
            organization="Transport Department",
        )
        self.db.add_all([self.manager_user, self.other_dept_user])
        self.db.commit()

        self.campaign = Campaign(
            name="Emergency Response Drive",
            campaign_type="Emergency Alert",
            objective="Emergency public alert",
            created_by=self.manager_user.id,
        )
        self.db.add(self.campaign)
        self.db.flush()

        self.asset = ContentAsset(
            title="Immediate Flood Alert",
            body="URGENT: Flooding alert for {city}! Evacuate immediately. Call emergency helpline 1077. Official updates at https://disaster.gov.in on 15/11/2026.",
            call_to_action="Call 1077 immediately",
            category="Disaster Preparedness",
            tone="urgent",
            channel="SMS",
            source_language="en",
            campaign_id=self.campaign.id,
            created_by=self.manager_user.id,
            review_status="Draft",
        )
        self.db.add(self.asset)
        self.db.commit()
        self.db.refresh(self.asset)

        self.manager_token = create_access_token(self.manager_user.id)
        self.other_token = create_access_token(self.other_dept_user.id)

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
        app.dependency_overrides.clear()

    def test_tone_analyze_success(self):
        headers = {"Authorization": f"Bearer {self.manager_token}"}
        res = self.client.post(f"/content/{self.asset.id}/tone/analyze", headers=headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()

        self.assertEqual(data["content_asset_id"], self.asset.id)
        self.assertIn(data["detected_tone"], ["Urgent", "Friendly", "Formal", "Harsh", "Neutral"])
        self.assertGreaterEqual(data["sentiment_polarity"], -1.0)
        self.assertLessEqual(data["sentiment_polarity"], 1.0)
        self.assertGreaterEqual(data["readability_score"], 0.0)
        self.assertLessEqual(data["readability_score"], 100.0)
        self.assertGreaterEqual(data["clarity_score"], 0.0)
        self.assertLessEqual(data["clarity_score"], 100.0)
        self.assertIn("tone_alignment", data)
        self.assertIn("formatting_anomalies", data)
        self.assertIn("suggestions", data)

    def test_tone_analyze_with_target_override(self):
        headers = {"Authorization": f"Bearer {self.manager_token}"}
        res = self.client.post(
            f"/content/{self.asset.id}/tone/analyze",
            headers=headers,
            json={"target_tone": "friendly"},
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["target_tone"], "friendly")
        self.assertTrue(data["tone_alignment"]["mismatch_detected"])

    def test_tone_improve_quick_adjustment_more_formal(self):
        headers = {"Authorization": f"Bearer {self.manager_token}"}
        res = self.client.post(
            f"/content/{self.asset.id}/tone/improve",
            headers=headers,
            json={"target_tone": "Formal", "adjustment_instruction": "more_formal"},
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()

        self.assertEqual(data["target_tone"], "Formal")
        self.assertIn("improved_content", data)
        self.assertIn("diff", data)
        self.assertIn(data["factual_preservation"]["status"], ("verified", "repaired"))
        self.assertIn("1077", data["improved_content"])
        self.assertIn("{city}", data["improved_content"])

    def test_tone_improve_quick_adjustment_friendlier(self):
        headers = {"Authorization": f"Bearer {self.manager_token}"}
        res = self.client.post(
            f"/content/{self.asset.id}/tone/improve",
            headers=headers,
            json={"target_tone": "Friendly", "adjustment_instruction": "friendlier"},
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue("Dear" in data["improved_content"] or "friend" in data["improved_content"].lower())
        self.assertIn("1077", data["improved_content"])

    def test_tone_improve_quick_adjustment_shorter(self):
        headers = {"Authorization": f"Bearer {self.manager_token}"}
        res = self.client.post(
            f"/content/{self.asset.id}/tone/improve",
            headers=headers,
            json={"target_tone": "Urgent", "adjustment_instruction": "shorter"},
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertNotEqual(data["diff"]["summary"], "")
        self.assertIn("1077", data["improved_content"])

    def test_tone_improve_preserves_emergency_helpline_and_date(self):
        headers = {"Authorization": f"Bearer {self.manager_token}"}
        res = self.client.post(
            f"/content/{self.asset.id}/tone/improve",
            headers=headers,
            json={"target_tone": "Formal", "adjustment_instruction": "more_formal"},
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        pres = data["factual_preservation"]
        self.assertIn("1077", pres["preserved_helplines"])
        self.assertIn("15/11/2026", pres["preserved_dates"])

    def test_unauthenticated_request_rejected(self):
        res = self.client.post(f"/content/{self.asset.id}/tone/analyze")
        self.assertEqual(res.status_code, 401)

    def test_nonexistent_asset_returns_404(self):
        headers = {"Authorization": f"Bearer {self.manager_token}"}
        res = self.client.post("/content/999999/tone/analyze", headers=headers)
        self.assertEqual(res.status_code, 404)

    def test_cross_organization_access_forbidden(self):
        headers = {"Authorization": f"Bearer {self.other_token}"}
        res = self.client.post(f"/content/{self.asset.id}/tone/analyze", headers=headers)
        self.assertEqual(res.status_code, 403)
