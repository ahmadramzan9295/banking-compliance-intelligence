"""
Test suite for the Banking Compliance & Risk Intelligence pipeline.

Run with:
    python -m pytest tests/ -v
or, dependency-free:
    python tests/test_pipeline.py
"""

import sys
import os
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.orchestrator import RegulatoryIntelligenceOrchestrator
from app.schemas.output_schema import validate_with_fallback, OUTPUT_JSON_SCHEMA
from app.agents.validation_agent import ValidationAgent
from app.agents.contradiction_agent import ContradictionDetectionAgent, _relative_delta_pct, _severity_for_delta
from app.agents.confidence_agent import compute_confidence_score
from app.agents.ingestion_agent import IngestionError


class TestSchemaValidation(unittest.TestCase):
    def test_valid_minimal_report_passes(self):
        report = {
            "jurisdiction": "US",
            "regulation_topic": "basel_iii_capital_requirements",
            "summary": "Test summary.",
            "key_rules": [],
            "contradictions": [],
            "confidence_score": 0.8,
            "citations": [],
            "version": "1.0.0",
            "timestamp": "2026-06-16T00:00:00+00:00",
            "audit_log_id": "AUD-test",
        }
        is_valid, errors = validate_with_fallback(report)
        self.assertTrue(is_valid, errors)

    def test_missing_field_fails(self):
        report = {
            "jurisdiction": "US",
            "regulation_topic": "basel_iii_capital_requirements",
            # "summary" missing
            "key_rules": [],
            "contradictions": [],
            "confidence_score": 0.8,
            "citations": [],
            "version": "1.0.0",
            "timestamp": "2026-06-16T00:00:00+00:00",
            "audit_log_id": "AUD-test",
        }
        is_valid, errors = validate_with_fallback(report)
        self.assertFalse(is_valid)
        self.assertTrue(any("summary" in e for e in errors))

    def test_confidence_score_out_of_range_fails(self):
        report = {
            "jurisdiction": "US",
            "regulation_topic": "basel_iii_capital_requirements",
            "summary": "Test summary.",
            "key_rules": [],
            "contradictions": [],
            "confidence_score": 1.5,  # invalid
            "citations": [],
            "version": "1.0.0",
            "timestamp": "2026-06-16T00:00:00+00:00",
            "audit_log_id": "AUD-test",
        }
        is_valid, errors = validate_with_fallback(report)
        self.assertFalse(is_valid)


class TestValidationAgent(unittest.TestCase):
    def setUp(self):
        self.agent = ValidationAgent()

    def test_record_with_missing_field_is_rejected(self):
        bad_record = {
            "jurisdiction": "US",
            "regulator": "Federal Reserve",
            "source_reliability": 0.9,
            "publication_date": "2025-01-01",
            "rule_key": "",  # empty -> invalid
            "title": "Some rule",
            "value": 4.5,
            "unit": "percent",
            "text": "Some text",
            "effective_date": "2025-01-01",
        }
        errors = self.agent._validate_record(bad_record)
        self.assertTrue(len(errors) > 0)

    def test_record_with_out_of_range_value_is_rejected(self):
        bad_record = {
            "jurisdiction": "US",
            "regulator": "Federal Reserve",
            "source_reliability": 0.9,
            "publication_date": "2025-01-01",
            "rule_key": "weird_rule",
            "title": "Weird rule",
            "value": 999.0,  # implausible percent
            "unit": "percent",
            "text": "Some text",
            "effective_date": "2025-01-01",
        }
        errors = self.agent._validate_record(bad_record)
        self.assertTrue(any("plausible" in e for e in errors))

    def test_valid_record_passes(self):
        good_record = {
            "jurisdiction": "US",
            "regulator": "Federal Reserve",
            "source_reliability": 0.9,
            "publication_date": "2025-01-01",
            "rule_key": "cet1_minimum_ratio",
            "title": "CET1",
            "value": 4.5,
            "unit": "percent",
            "text": "Some text",
            "effective_date": "2025-01-01",
        }
        errors = self.agent._validate_record(good_record)
        self.assertEqual(errors, [])


class TestContradictionDetection(unittest.TestCase):
    def test_relative_delta_and_severity(self):
        self.assertAlmostEqual(_relative_delta_pct(5.0, 5.0), 0.0)
        self.assertEqual(_severity_for_delta(5.0), "low")
        self.assertEqual(_severity_for_delta(15.0), "medium")
        self.assertEqual(_severity_for_delta(40.0), "high")

    def test_known_us_eu_leverage_ratio_contradiction_detected(self):
        orchestrator = RegulatoryIntelligenceOrchestrator()
        report = orchestrator.run("US", "basel_iii_capital_requirements")
        leverage_contradictions = [
            c for c in report["contradictions"] if c["rule_key"] == "supplementary_leverage_ratio"
        ]
        self.assertTrue(len(leverage_contradictions) >= 1)
        self.assertEqual(leverage_contradictions[0]["severity"], "high")


class TestConfidenceScoring(unittest.TestCase):
    def test_score_is_between_zero_and_one(self):
        primary_records = [
            {"rule_key": "a", "source_reliability": 0.9},
            {"rule_key": "b", "source_reliability": 0.8},
        ]
        validated_records = {"US": primary_records, "EU": [{"rule_key": "a", "source_reliability": 0.7}]}
        contradictions = [{"severity": "high"}]
        result = compute_confidence_score(primary_records, validated_records, contradictions, "US")
        self.assertGreaterEqual(result["confidence_score"], 0.0)
        self.assertLessEqual(result["confidence_score"], 1.0)

    def test_no_contradictions_yields_higher_score_than_with_contradictions(self):
        primary_records = [{"rule_key": "a", "source_reliability": 0.9}]
        validated_records = {"US": primary_records, "EU": [{"rule_key": "a", "source_reliability": 0.9}]}
        score_clean = compute_confidence_score(primary_records, validated_records, [], "US")
        score_with_issue = compute_confidence_score(
            primary_records, validated_records, [{"severity": "high"}], "US"
        )
        self.assertGreater(score_clean["confidence_score"], score_with_issue["confidence_score"])


class TestFullPipelineReproducibility(unittest.TestCase):
    def test_same_input_produces_same_deterministic_content(self):
        orchestrator = RegulatoryIntelligenceOrchestrator()
        report1 = orchestrator.run("US", "basel_iii_capital_requirements")
        report2 = orchestrator.run("US", "basel_iii_capital_requirements")

        for key in ("timestamp", "audit_log_id"):
            report1.pop(key)
            report2.pop(key)

        self.assertEqual(report1, report2)

    def test_unknown_jurisdiction_raises_ingestion_error(self):
        orchestrator = RegulatoryIntelligenceOrchestrator()
        with self.assertRaises(IngestionError):
            orchestrator.run("ZZ", "basel_iii_capital_requirements")

    def test_final_output_conforms_to_strict_schema(self):
        orchestrator = RegulatoryIntelligenceOrchestrator()
        report = orchestrator.run("EU", "basel_iii_capital_requirements")
        is_valid, errors = validate_with_fallback(report)
        self.assertTrue(is_valid, errors)
        self.assertEqual(set(report.keys()), set(OUTPUT_JSON_SCHEMA["required"]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
