"""
Agent 1: Data Ingestion Agent
------------------------------
Responsible for retrieving raw regulatory data for the requested
jurisdiction *and* its registered peer jurisdictions on the same topic
(peers are required downstream for contradiction detection).

In this sample project, sources are local JSON files acting as stand-ins
for live regulator feeds / document stores. Swapping in a real connector
(API pull, S3 fetch, vendor feed) only requires changing `_load_source`;
the rest of the pipeline is unaffected — this is the system's primary
extension point for new data sources.
"""

from __future__ import annotations
import json
from typing import Any, Dict

from app.agents.base import BaseAgent
from app.registry.jurisdiction_registry import registry


class IngestionError(Exception):
    pass


class DataIngestionAgent(BaseAgent):
    name = "data_ingestion_agent"

    def _load_source(self, file_path: str) -> Dict[str, Any]:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError as exc:
            raise IngestionError(f"Source file not found: {file_path}") from exc
        except json.JSONDecodeError as exc:
            raise IngestionError(f"Malformed source JSON at {file_path}: {exc}") from exc

    def process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        jurisdiction = context["request"]["jurisdiction"].upper()
        topic = context["request"]["regulation_topic"]

        primary_path = registry.get_source_path(jurisdiction, topic)
        if not primary_path:
            raise IngestionError(
                f"No registered data source for jurisdiction='{jurisdiction}' "
                f"topic='{topic}'. Registered jurisdictions: "
                f"{registry.list_jurisdictions(topic)}"
            )

        raw_sources = {jurisdiction: self._load_source(primary_path)}

        peer_jurisdictions = registry.get_peer_jurisdictions(jurisdiction, topic)
        for peer in peer_jurisdictions:
            peer_path = registry.get_source_path(peer, topic)
            if peer_path:
                try:
                    raw_sources[peer] = self._load_source(peer_path)
                except IngestionError as exc:
                    # A missing peer source degrades cross-validation but
                    # should not fail the whole pipeline.
                    self.logger.warning(f"peer_source_skipped jurisdiction='{peer}' error='{exc}'")

        context["raw_sources"] = raw_sources
        context["primary_jurisdiction"] = jurisdiction
        context["topic"] = topic
        self.logger.info(
            f"ingested sources for jurisdictions={list(raw_sources.keys())} topic='{topic}'"
        )
        return context
