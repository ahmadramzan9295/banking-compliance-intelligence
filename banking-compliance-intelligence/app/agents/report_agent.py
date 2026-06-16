"""
Agent 6: Report Generation Agent
------------------------------------
Assembles the final, strict-format JSON output from accumulated pipeline
context. This is the only agent that touches the output contract — every
other agent works with internal intermediate shapes. Before returning,
the assembled report is validated against OUTPUT_JSON_SCHEMA one more
time as a final safety net; if it fails, the pipeline raises rather than
silently returning a non-conformant payload.
"""

from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Dict, List

from app.agents.base import BaseAgent
from app.schemas.output_schema import validate_with_fallback, SchemaValidationError

PIPELINE_VERSION = "1.0.0"


def _build_summary(primary: str, topic: str, key_rules: List[Dict[str, Any]], contradictions: List[Dict[str, Any]]) -> str:
    rule_count = len(key_rules)
    contradiction_count = len(contradictions)
    topic_readable = topic.replace("_", " ")
    base = (
        f"{primary} maintains {rule_count} core requirement(s) under {topic_readable}."
    )
    if contradiction_count == 0:
        return base + " No material divergence was found versus peer jurisdictions on the compared rules."
    high = sum(1 for c in contradictions if c["severity"] == "high")
    medium = sum(1 for c in contradictions if c["severity"] == "medium")
    low = sum(1 for c in contradictions if c["severity"] == "low")
    return (
        base
        + f" {contradiction_count} cross-jurisdiction divergence(s) were identified "
        f"({high} high, {medium} medium, {low} low severity), detailed in 'contradictions'."
    )


class ReportGenerationAgent(BaseAgent):
    name = "report_generation_agent"

    def process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        primary = context["primary_jurisdiction"]
        topic = context["topic"]
        primary_records = context["validated_records"].get(primary, [])
        contradictions = context["contradictions"]
        confidence_result = context["confidence_result"]
        audit_log_id = context["audit_log_id"]

        key_rules = [
            {
                "rule_key": r["rule_key"],
                "title": r["title"],
                "value": r["value"],
                "unit": r["unit"],
                "description": r["text"],
            }
            for r in primary_records
        ]

        citations = []
        seen_sources = set()
        for jurisdiction, records in context["validated_records"].items():
            for r in records:
                source_key = (r["jurisdiction"], r["regulator"], r["publication_date"])
                if source_key in seen_sources:
                    continue
                seen_sources.add(source_key)
                citations.append(
                    {
                        "source": f"{r['jurisdiction']} regulatory source",
                        "regulator": r["regulator"],
                        "publication_date": r["publication_date"],
                        "reliability": r["source_reliability"],
                    }
                )

        report = {
            "jurisdiction": primary,
            "regulation_topic": topic,
            "summary": _build_summary(primary, topic, key_rules, contradictions),
            "key_rules": key_rules,
            "contradictions": contradictions,
            "confidence_score": confidence_result["confidence_score"],
            "citations": citations,
            "version": PIPELINE_VERSION,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "audit_log_id": audit_log_id,
        }

        is_valid, errors = validate_with_fallback(report)
        if not is_valid:
            self.logger.error(f"final_report_failed_schema_validation errors={errors}")
            raise SchemaValidationError(errors)

        context["final_report"] = report
        self.logger.info(f"report generated and schema-validated for jurisdiction='{primary}'")
        return context
