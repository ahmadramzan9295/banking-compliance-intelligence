"""
Orchestrator
------------
Drives the six agents through a fixed, deterministic sequence:

  Ingestion -> Normalization -> Validation -> Contradiction Detection
  -> Confidence Scoring -> Report Generation

No agent is invoked conditionally and no step uses non-deterministic
sampling — the same input always produces the same output_hash, which
is the core audit/reproducibility guarantee for this system.

This intentionally mirrors a LangChain-style sequential chain without
adopting LangChain's non-determinism-prone abstractions (e.g. agentic
tool-choice loops) — every transition here is explicit and inspectable.
"""

from __future__ import annotations
from typing import Any, Dict

from app.agents.ingestion_agent import DataIngestionAgent
from app.agents.normalization_agent import NormalizationAgent
from app.agents.validation_agent import ValidationAgent
from app.agents.contradiction_agent import ContradictionDetectionAgent
from app.agents.confidence_agent import ConfidenceScoringAgent
from app.agents.report_agent import ReportGenerationAgent, PIPELINE_VERSION
from app.audit.audit_logger import AuditLogger, new_audit_log_id
from app.utils.logging_config import get_logger

logger = get_logger("orchestrator")


class RegulatoryIntelligenceOrchestrator:
    def __init__(self):
        self.ingestion_agent = DataIngestionAgent()
        self.normalization_agent = NormalizationAgent()
        self.validation_agent = ValidationAgent()
        self.contradiction_agent = ContradictionDetectionAgent()
        self.confidence_agent = ConfidenceScoringAgent()
        self.report_agent = ReportGenerationAgent()

    def run(self, jurisdiction: str, regulation_topic: str) -> Dict[str, Any]:
        audit_log_id = new_audit_log_id()
        audit_logger = AuditLogger()

        input_payload = {"jurisdiction": jurisdiction, "regulation_topic": regulation_topic}
        context: Dict[str, Any] = {"request": input_payload, "audit_log_id": audit_log_id}

        logger.info(f"pipeline_run_start audit_log_id='{audit_log_id}' input={input_payload}")

        pipeline = [
            self.ingestion_agent,
            self.normalization_agent,
            self.validation_agent,
            self.contradiction_agent,
            self.confidence_agent,
            self.report_agent,
        ]

        for agent in pipeline:
            context = agent.run(context)

        for timing in context.get("_stage_timings", []):
            audit_logger.record_stage(timing["stage"], timing["duration_ms"])

        final_report = context["final_report"]

        audit_logger.commit(
            audit_log_id=audit_log_id,
            pipeline_version=PIPELINE_VERSION,
            input_payload=input_payload,
            output_payload=final_report,
            rejected_records=context.get("rejected_records", []),
        )

        logger.info(f"pipeline_run_complete audit_log_id='{audit_log_id}'")
        return final_report
