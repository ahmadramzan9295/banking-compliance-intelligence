"""
Agent 5: Confidence Scoring Agent
------------------------------------
Deterministic weighted score in [0, 1], computed from three signals:

1. Source reliability (weight 0.40)
   Average declared reliability of all sources contributing to the
   primary jurisdiction's records.

2. Data consistency (weight 0.35)
   1 - (contradiction penalty), where each contradiction reduces
   consistency proportional to its severity (high=0.15, medium=0.08,
   low=0.03 penalty per contradiction), floored at 0.

3. Cross-validation coverage (weight 0.25)
   Fraction of the primary jurisdiction's rules that have at least one
   peer jurisdiction record for the same rule_key (i.e. could be
   cross-checked at all, regardless of whether they matched).

Because every input to this function is itself deterministic (no LLM
sampling), the same inputs always produce the same score — required for
audit reproducibility.
"""

from __future__ import annotations
from typing import Any, Dict, List

from app.agents.base import BaseAgent

WEIGHT_RELIABILITY = 0.40
WEIGHT_CONSISTENCY = 0.35
WEIGHT_CROSS_VALIDATION = 0.25

SEVERITY_PENALTY = {"high": 0.15, "medium": 0.08, "low": 0.03}


def compute_confidence_score(
    primary_records: List[Dict[str, Any]],
    validated_records: Dict[str, List[Dict[str, Any]]],
    contradictions: List[Dict[str, Any]],
    primary_jurisdiction: str,
) -> Dict[str, Any]:
    # 1. Source reliability
    if primary_records:
        reliability_avg = sum(r["source_reliability"] for r in primary_records) / len(primary_records)
    else:
        reliability_avg = 0.0

    # 2. Data consistency
    consistency_penalty = sum(SEVERITY_PENALTY.get(c["severity"], 0.05) for c in contradictions)
    consistency_score = max(0.0, 1.0 - consistency_penalty)

    # 3. Cross-validation coverage
    peer_keys = set()
    for jurisdiction, records in validated_records.items():
        if jurisdiction == primary_jurisdiction:
            continue
        peer_keys.update(r["rule_key"] for r in records)

    primary_keys = [r["rule_key"] for r in primary_records]
    if primary_keys:
        covered = sum(1 for k in primary_keys if k in peer_keys)
        cross_validation_score = covered / len(primary_keys)
    else:
        cross_validation_score = 0.0

    raw_score = (
        WEIGHT_RELIABILITY * reliability_avg
        + WEIGHT_CONSISTENCY * consistency_score
        + WEIGHT_CROSS_VALIDATION * cross_validation_score
    )
    final_score = round(min(1.0, max(0.0, raw_score)), 4)

    return {
        "confidence_score": final_score,
        "components": {
            "source_reliability_avg": round(reliability_avg, 4),
            "consistency_score": round(consistency_score, 4),
            "cross_validation_score": round(cross_validation_score, 4),
            "weights": {
                "reliability": WEIGHT_RELIABILITY,
                "consistency": WEIGHT_CONSISTENCY,
                "cross_validation": WEIGHT_CROSS_VALIDATION,
            },
        },
    }


class ConfidenceScoringAgent(BaseAgent):
    name = "confidence_scoring_agent"

    def process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        primary = context["primary_jurisdiction"]
        validated_records = context["validated_records"]
        primary_records = validated_records.get(primary, [])
        contradictions = context["contradictions"]

        result = compute_confidence_score(primary_records, validated_records, contradictions, primary)
        context["confidence_result"] = result
        self.logger.info(
            f"confidence_score={result['confidence_score']} components={result['components']}"
        )
        return context
