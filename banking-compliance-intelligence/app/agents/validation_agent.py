"""
Agent 3: Validation Agent
---------------------------
Two layers of validation, both enforced before any record is allowed
further into the pipeline:

1. Structural validation — required fields present, correct types.
2. Rule-based business validation — domain-specific sanity checks
   (e.g. percentage ratios must fall in a plausible range, dates must
   parse, jurisdiction codes must be known, rule_key must be non-empty).

Invalid records are REJECTED (not silently dropped) — they're recorded
in context["rejected_records"] with explicit reasons and surfaced in
the audit log, satisfying "ensure no missing fields" and "reject invalid
outputs" without crashing the whole pipeline run.
"""

from __future__ import annotations
from datetime import datetime
from typing import Any, Dict, List

from app.agents.base import BaseAgent

PLAUSIBLE_RATIO_RANGE = (0.0, 200.0)  # percent; generous bound to catch obvious data errors
KNOWN_JURISDICTIONS = {"US", "EU", "UK", "SG", "JP", "CA", "AU"}


class ValidationAgent(BaseAgent):
    name = "validation_agent"

    def _validate_record(self, record: Dict[str, Any]) -> List[str]:
        errors: List[str] = []

        required_fields = ["jurisdiction", "rule_key", "title", "value", "unit", "text"]
        for field in required_fields:
            if record.get(field) in (None, ""):
                errors.append(f"missing or empty required field '{field}'")

        if record.get("jurisdiction") and record["jurisdiction"] not in KNOWN_JURISDICTIONS:
            errors.append(
                f"jurisdiction '{record['jurisdiction']}' not in known registry "
                f"{sorted(KNOWN_JURISDICTIONS)}"
            )

        value = record.get("value")
        if value is not None:
            if not isinstance(value, (int, float)):
                errors.append("value is not numeric")
            elif record.get("unit") == "percent" and not (
                PLAUSIBLE_RATIO_RANGE[0] <= value <= PLAUSIBLE_RATIO_RANGE[1]
            ):
                errors.append(
                    f"value {value} outside plausible percent range {PLAUSIBLE_RATIO_RANGE}"
                )

        effective_date = record.get("effective_date")
        if effective_date:
            try:
                datetime.strptime(effective_date, "%Y-%m-%d")
            except ValueError:
                errors.append(f"effective_date '{effective_date}' is not valid ISO format (YYYY-MM-DD)")

        return errors

    def process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        normalized: Dict[str, List[Dict[str, Any]]] = context["normalized_records"]

        valid_records: Dict[str, List[Dict[str, Any]]] = {}
        rejected_records: List[Dict[str, Any]] = []

        for jurisdiction, records in normalized.items():
            kept = []
            for record in records:
                errors = self._validate_record(record)
                if errors:
                    rejected_records.append({"record": record, "errors": errors})
                    self.logger.warning(
                        f"record_rejected jurisdiction='{jurisdiction}' "
                        f"rule_key='{record.get('rule_key')}' errors={errors}"
                    )
                else:
                    kept.append(record)
            valid_records[jurisdiction] = kept

        context["validated_records"] = valid_records
        context["rejected_records"] = rejected_records

        primary = context["primary_jurisdiction"]
        if not valid_records.get(primary):
            raise ValueError(
                f"All records for primary jurisdiction '{primary}' failed validation; "
                f"cannot proceed. Rejected: {rejected_records}"
            )

        self.logger.info(
            f"validation complete: "
            f"{sum(len(v) for v in valid_records.values())} valid, "
            f"{len(rejected_records)} rejected"
        )
        return context
