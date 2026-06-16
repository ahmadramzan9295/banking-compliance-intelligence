"""
Audit Logger
------------
Every pipeline run is recorded as an immutable, append-only JSONL entry
containing: a unique audit_log_id, UTC timestamp, pipeline version,
SHA-256 hashes of the input and output (for tamper-evidence and
reproducibility checks), per-stage durations, and the full input/output
payloads for compliance review.

Reproducibility contract: given the same input and the same pipeline
version, re-running the pipeline against unchanged source data must
produce an identical output_hash. If source data changes, the hash
changes, and the audit trail shows exactly when and why.
"""

from __future__ import annotations
import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.utils.logging_config import get_logger

logger = get_logger("audit.logger")

AUDIT_LOG_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "logs"
)
AUDIT_LOG_FILE = os.path.join(AUDIT_LOG_DIR, "audit_trail.jsonl")
os.makedirs(AUDIT_LOG_DIR, exist_ok=True)


def _canonical_hash(payload: Any) -> str:
    """Deterministic SHA-256 hash of a JSON-serializable payload.
    Keys are sorted so equivalent dicts always hash identically."""
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def new_audit_log_id() -> str:
    return f"AUD-{uuid.uuid4()}"


class AuditLogger:
    def __init__(self, log_file: str = AUDIT_LOG_FILE):
        self.log_file = log_file
        self._stage_timings: List[Dict[str, Any]] = []

    def record_stage(self, stage_name: str, duration_ms: float, status: str = "success") -> None:
        self._stage_timings.append(
            {"stage": stage_name, "duration_ms": round(duration_ms, 3), "status": status}
        )
        logger.info(f"stage='{stage_name}' status='{status}' duration_ms={round(duration_ms, 3)}")

    def commit(
        self,
        audit_log_id: str,
        pipeline_version: str,
        input_payload: Dict[str, Any],
        output_payload: Dict[str, Any],
        rejected_records: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        # content_hash excludes volatile per-run fields (timestamp, audit_log_id)
        # so it captures only the deterministic regulatory CONTENT. Re-running
        # the pipeline against unchanged source data must reproduce an
        # identical content_hash even though output_hash/timestamp differ.
        content_for_hash = {
            k: v for k, v in output_payload.items() if k not in ("timestamp", "audit_log_id")
        }
        entry = {
            "audit_log_id": audit_log_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "pipeline_version": pipeline_version,
            "input": input_payload,
            "input_hash": _canonical_hash(input_payload),
            "output": output_payload,
            "output_hash": _canonical_hash(output_payload),
            "content_hash": _canonical_hash(content_for_hash),
            "stage_timings": self._stage_timings,
            "rejected_records": rejected_records or [],
        }
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
        logger.info(
            f"audit_log_id={audit_log_id} committed | input_hash={entry['input_hash'][:12]}... "
            f"output_hash={entry['output_hash'][:12]}..."
        )
        return entry

    @staticmethod
    def lookup(audit_log_id: str, log_file: str = AUDIT_LOG_FILE) -> Optional[Dict[str, Any]]:
        """Retrieve a past audit entry by ID — used to reproduce or verify
        a prior run for compliance/regulatory examination."""
        if not os.path.exists(log_file):
            return None
        with open(log_file, "r", encoding="utf-8") as f:
            for line in f:
                entry = json.loads(line)
                if entry.get("audit_log_id") == audit_log_id:
                    return entry
        return None
