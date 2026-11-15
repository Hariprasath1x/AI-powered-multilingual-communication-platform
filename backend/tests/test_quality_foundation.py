"""Unit tests for Task 8, Checkpoint 1: Quality Engine Foundation & Deterministic Rules."""

import unittest
import asyncio
from app.services.quality.base import (
    FindingCategory,
    FindingSeverity,
    EvaluationSource,
    AssessmentStatus,
    ContentQualityFindingDTO,
)
from app.services.quality.rule_engine import (
    DeterministicRuleEngine,
    extract_numbers_and_helplines,
)
from app.services.quality.scoring import calculate_quality_score
from app.services.ai.base import (
    ContentEvaluationRequest,
    AIProviderError,
    AIProviderTimeoutError,
)
from app.services.ai.mock_provider import MockAIProvider


class TestQualityEngineFoundation(unittest.TestCase):
    """Test suite for deterministic compliance rules, scoring algorithms, and AI evaluator."""

    # -------------------------------------------------------------
    # 1. Deterministic Completeness Rules
    # -------------------------------------------------------------

    def test_completeness_missing_title_and_body(self):
        """Missing title or empty body triggers CRITICAL completeness findings."""
        findings = DeterministicRuleEngine.evaluate(
            title="",
            body="Short",
            call_to_action="Click here",
            channel="Email",
            source_language="en",
        )
        severities = [f.severity for f in findings if f.category == FindingCategory.COMPLETENESS]
        self.assertIn(FindingSeverity.CRITICAL, severities)

        rule_ids = [f.rule_id for f in findings]
        self.assertIn("RULE-COMP-001", rule_ids)
        self.assertIn("RULE-COMP-002", rule_ids)

    # -------------------------------------------------------------
    # 2. Deterministic Placeholder Rules
    # -------------------------------------------------------------

    def test_placeholder_malformed_syntax(self):
        """Mismatched curly braces triggers CRITICAL placeholder finding."""
        findings = DeterministicRuleEngine.evaluate(
            title="Notice for citizens",
            body="Dear {name, please visit {city} center.",
            call_to_action="Visit now",
            channel="SMS",
            source_language="en",
        )
        malformed = [f for f in findings if f.rule_id == "RULE-PH-001"]
        self.assertEqual(len(malformed), 1)
        self.assertEqual(malformed[0].severity, FindingSeverity.CRITICAL)

    def test_placeholder_unsupported_token(self):
        """Unsupported placeholder token outside allowlist triggers HIGH finding."""
        findings = DeterministicRuleEngine.evaluate(
            title="Update",
            body="Citizen {name}, your account balance is {account_balance}.",
            call_to_action="Check account",
            channel="Email",
            source_language="en",
        )
        unsupported = [f for f in findings if f.rule_id == "RULE-PH-002"]
        self.assertEqual(len(unsupported), 1)
        self.assertEqual(unsupported[0].severity, FindingSeverity.HIGH)
        self.assertIn("{account_balance}", unsupported[0].title)

    def test_placeholder_dropped_in_translation(self):
        """Dropping a source placeholder in translation triggers CRITICAL finding."""
        findings = DeterministicRuleEngine.evaluate(
            title="Tamil Alert",
            body="மக்களுக்கான எச்சரிக்கை செய்தி.",  # {name} and {city} dropped!
            call_to_action="தொடர்பு கொள்ளவும்",
            channel="SMS",
            source_language="ta",
            target_language="ta",
            parent_title="English Alert",
            parent_body="Dear {name}, critical alert for residents of {city}.",
            parent_cta="Contact now",
        )
        dropped = [f for f in findings if f.rule_id == "RULE-PH-003"]
        self.assertEqual(len(dropped), 1)
        self.assertEqual(dropped[0].severity, FindingSeverity.CRITICAL)
        self.assertIn("{name}", dropped[0].explanation)
        self.assertIn("{city}", dropped[0].explanation)

    # -------------------------------------------------------------
    # 3. Channel Compliance Rules
    # -------------------------------------------------------------

    def test_sms_segment_and_length_warnings(self):
        """SMS over 3 segments triggers HIGH warning; over 1600 chars triggers CRITICAL."""
        # 500 characters ASCII = 4 segments (>3 segments)
        long_sms = "Important announcement for all citizens. " * 12
        findings = DeterministicRuleEngine.evaluate(
            title="SMS Notice",
            body=long_sms,
            call_to_action="Call helpline",
            channel="SMS",
            source_language="en",
        )
        chan_findings = [f for f in findings if f.category == FindingCategory.CHANNEL]
        self.assertTrue(any(f.rule_id == "RULE-CHAN-SMS-001" for f in chan_findings))

    def test_voice_script_url_and_duration_check(self):
        """Voice scripts containing clickable URLs or duration >90s trigger findings."""
        voice_body = "Attention residents. Please visit https://disaster.gov.in/portal/emergency immediately for help."
        findings = DeterministicRuleEngine.evaluate(
            title="IVR Script",
            body=voice_body,
            call_to_action="Press 1 to repeat",
            channel="Voice",
            source_language="en",
        )
        url_findings = [f for f in findings if f.rule_id == "RULE-CHAN-VOICE-002"]
        self.assertEqual(len(url_findings), 1)
        self.assertEqual(url_findings[0].severity, FindingSeverity.MEDIUM)

    # -------------------------------------------------------------
    # 4. Factual Anchors & Emergency Helplines
    # -------------------------------------------------------------

    def test_factual_omission_of_verified_emergency_helpline(self):
        """Omitting verified helpline (e.g. 1070) provided in facts triggers CRITICAL factual finding."""
        facts = "State disaster control room 24x7 helpline: 1070. Free shelters open."
        body_without_helpline = "Dear {name}, severe cyclone alert in {city}. Free shelters are open at school."

        findings = DeterministicRuleEngine.evaluate(
            title="Cyclone Warning",
            body=body_without_helpline,
            call_to_action="Seek shelter",
            channel="SMS",
            source_language="en",
            reference_facts=facts,
        )
        fact_findings = [f for f in findings if f.rule_id == "RULE-FACT-001"]
        self.assertEqual(len(fact_findings), 1)
        self.assertEqual(fact_findings[0].severity, FindingSeverity.CRITICAL)
        self.assertIn("1070", fact_findings[0].title)

    # -------------------------------------------------------------
    # 5. Sensitive & Panic Content
    # -------------------------------------------------------------

    def test_sensitive_panic_wording_detected(self):
        """Panic-inducing terms like 'everyone will die' trigger CRITICAL safety finding."""
        panic_text = "Urgent: massive disaster ahead. Apocalypse is coming, everyone will die if you do not leave now!"
        findings = DeterministicRuleEngine.evaluate(
            title="Warning",
            body=panic_text,
            call_to_action="Run",
            channel="SMS",
            source_language="en",
        )
        safety_findings = [f for f in findings if f.category == FindingCategory.SAFETY_SENSITIVE]
        self.assertTrue(len(safety_findings) >= 1)
        self.assertEqual(safety_findings[0].severity, FindingSeverity.CRITICAL)

    # -------------------------------------------------------------
    # 6. Quality Scoring & Safety Override
    # -------------------------------------------------------------

    def test_scoring_clean_asset_gets_high_score(self):
        """Content with zero findings receives 100.0 score and COMPLETED status."""
        overall, dims, status, counts = calculate_quality_score(findings=[], is_translation=False)
        self.assertEqual(overall, 100.0)
        self.assertEqual(status, AssessmentStatus.COMPLETED)
        self.assertEqual(counts["critical"], 0)
        self.assertIsNone(dims.translation_consistency)  # Dynamic re-normalization for non-translation

    def test_scoring_safety_override_caps_score_on_critical_finding(self):
        """Safety Override: Even if only one critical issue occurs, overall score is capped at <= 49.0."""
        crit_finding = ContentQualityFindingDTO(
            category=FindingCategory.FACTUAL,
            severity=FindingSeverity.CRITICAL,
            title="Missing emergency helpline",
            explanation="1070 was omitted",
        )
        overall, dims, status, counts = calculate_quality_score(
            findings=[crit_finding],
            is_translation=False,
        )
        self.assertLessEqual(overall, 49.0)
        self.assertEqual(status, AssessmentStatus.COMPLETED_WITH_WARNINGS)
        self.assertEqual(counts["critical"], 1)

    def test_scoring_translation_re_normalization(self):
        """When is_translation=True, translation_consistency dimension is evaluated and weighted."""
        trans_finding = ContentQualityFindingDTO(
            category=FindingCategory.TRANSLATION,
            severity=FindingSeverity.HIGH,
            title="Translation tone drift",
            explanation="Tone shifted from urgent to casual",
        )
        overall, dims, status, counts = calculate_quality_score(
            findings=[trans_finding],
            is_translation=True,
        )
        self.assertIsNotNone(dims.translation_consistency)
        self.assertEqual(dims.translation_consistency, 80.0)  # 100 - 20 = 80
        self.assertEqual(counts["high"], 1)

    # -------------------------------------------------------------
    # 7. Mock AI Provider Evaluation
    # -------------------------------------------------------------

    def test_mock_ai_evaluation_tone_mismatch(self):
        """Mock AI evaluator detects tone mismatches and simulated hooks."""
        provider = MockAIProvider()

        req = ContentEvaluationRequest(
            title="Emergency Advisory",
            body="Everything is fine. Please carry on normally with your routine day.",
            category="Emergency Alert",
            tone="urgent",
            channel="SMS",
            source_language="en",
        )
        res = asyncio.run(provider.evaluate_content(req))

        self.assertIsInstance(res.findings, list)
        tone_findings = [f for f in res.findings if f.category == "tone"]
        self.assertEqual(len(tone_findings), 1)
        self.assertEqual(tone_findings[0].severity, "medium")

    def test_mock_ai_evaluation_timeout_simulation(self):
        """Simulate timeout hook raises AIProviderTimeoutError."""
        provider = MockAIProvider()
        req = ContentEvaluationRequest(
            title="[SIMULATE_TIMEOUT] Advisory",
            body="Testing timeout error",
            category="Healthcare",
            tone="informative",
            channel="Email",
            source_language="en",
        )
        with self.assertRaises(AIProviderTimeoutError):
            asyncio.run(provider.evaluate_content(req))


if __name__ == "__main__":
    unittest.main()

