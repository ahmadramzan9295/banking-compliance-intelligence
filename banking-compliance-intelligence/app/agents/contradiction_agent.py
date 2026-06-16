"""
Agent 4: Contradiction Detection Agent
-----------------------------------------
Compares the primary jurisdiction's rules against every peer
jurisdiction's rules on the same rule_key. A contradiction is flagged
when numeric values diverge beyond a tolerance threshold — this is the
core "regulatory divergence" signal a global bank's compliance desk
needs (e.g. "our UK leverage ratio requirement is stricter than the EU's
for the same rule").

Severity is deterministic, derived from the relative delta:
  - low:    delta_pct < 10%
  - medium: 10% <= delta_pct < 30%
  - high:   delta_pct >= 30%
"""

from __future__ import annotations
from typing import Any, Dict, List

from app.agents.base import BaseAgent

TOLERANCE_PCT = 1.0  # values within 1% relative difference are NOT contradictions


def _relative_delta_pct(a: float, b: float) -> float:
    if a == 0 and b == 0:
        return 0.0
    denom = max(abs(a), abs(b), 1e-9)
    return abs(a - b) / denom * 100.0


def _severity_for_delta(delta_pct: float) -> str:
    if delta_pct < 10.0:
        return "low"
    if delta_pct < 30.0:
        return "medium"
    return "high"


class ContradictionDetectionAgent(BaseAgent):
    name = "contradiction_detection_agent"

    def process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        validated: Dict[str, List[Dict[str, Any]]] = context["validated_records"]
        primary = context["primary_jurisdiction"]
        primary_records = {r["rule_key"]: r for r in validated.get(primary, [])}

        contradictions: List[Dict[str, Any]] = []

        for peer_jurisdiction, peer_records in validated.items():
            if peer_jurisdiction == primary:
                continue
            peer_by_key = {r["rule_key"]: r for r in peer_records}

            shared_keys = set(primary_records.keys()) & set(peer_by_key.keys())
            for rule_key in sorted(shared_keys):
                a = primary_records[rule_key]
                b = peer_by_key[rule_key]
                if a["value"] is None or b["value"] is None:
                    continue

                delta_pct = _relative_delta_pct(a["value"], b["value"])
                if delta_pct > TOLERANCE_PCT:
                    severity = _severity_for_delta(delta_pct)
                    contradictions.append(
                        {
                            "rule_key": rule_key,
                            "jurisdiction_a": primary,
                            "value_a": a["value"],
                            "jurisdiction_b": peer_jurisdiction,
                            "value_b": b["value"],
                            "severity": severity,
                            "description": (
                                f"{primary} requires {a['value']}{a['unit'] and '%' or ''} for "
                                f"'{a['title']}', while {peer_jurisdiction} requires "
                                f"{b['value']}{b['unit'] and '%' or ''} for the equivalent rule "
                                f"('{b['title']}') — a {delta_pct:.1f}% relative divergence."
                            ),
                        }
                    )

        context["contradictions"] = contradictions
        self.logger.info(f"contradiction_detection complete: {len(contradictions)} flagged")
        return context
