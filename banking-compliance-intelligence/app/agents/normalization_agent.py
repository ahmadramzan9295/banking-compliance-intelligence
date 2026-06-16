"""
Agent 2: Normalization Agent
------------------------------
Standardizes raw, source-specific JSON into a single canonical record
shape so downstream agents never need to know about source-specific
quirks (field naming, units, nesting). This isolation is what lets the
ingestion layer absorb new source formats without changing validation,
contradiction detection, or scoring logic.

Canonical normalized record shape:
{
  "jurisdiction": str,
  "regulator": str,
  "source_reliability": float,
  "publication_date": str,
  "rule_key": str,
  "title": str,
  "value": float,
  "unit": str,
  "text": str,
  "effective_date": str
}
"""

from __future__ import annotations
from typing import Any, Dict, List

from app.agents.base import BaseAgent


class NormalizationAgent(BaseAgent):
    name = "normalization_agent"

    def _normalize_one_source(self, source_doc: Dict[str, Any]) -> List[Dict[str, Any]]:
        jurisdiction = source_doc.get("jurisdiction", "UNKNOWN")
        regulator = source_doc.get("regulator", "UNKNOWN")
        reliability = float(source_doc.get("source_reliability", 0.5))
        pub_date = source_doc.get("publication_date", "")

        normalized_records = []
        for rule in source_doc.get("rules", []):
            normalized_records.append(
                {
                    "jurisdiction": jurisdiction,
                    "regulator": regulator,
                    "source_reliability": reliability,
                    "publication_date": pub_date,
                    "rule_key": (rule.get("rule_key") or "").strip().lower(),
                    "title": (rule.get("title") or "").strip(),
                    "value": float(rule["value"]) if rule.get("value") is not None else None,
                    "unit": (rule.get("unit") or "").strip(),
                    "text": (rule.get("text") or "").strip(),
                    "effective_date": rule.get("effective_date", ""),
                }
            )
        return normalized_records

    def process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        raw_sources = context["raw_sources"]
        normalized: Dict[str, List[Dict[str, Any]]] = {}
        for jurisdiction, source_doc in raw_sources.items():
            normalized[jurisdiction] = self._normalize_one_source(source_doc)

        context["normalized_records"] = normalized
        total = sum(len(v) for v in normalized.values())
        self.logger.info(f"normalized {total} records across {len(normalized)} jurisdiction(s)")
        return context
