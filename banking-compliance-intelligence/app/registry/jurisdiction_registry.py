"""
Jurisdiction & Data Source Registry
------------------------------------
Central, extensible registry mapping jurisdictions to their regulatory
data source files. New jurisdictions or topics are added here without
touching agent logic — this is the system's extension point.

To add a new jurisdiction:
    registry.register_source("SG", "basel_iii_capital_requirements",
                              "app/data/sample_sources/sg_basel_iii.json")

To add a brand new topic, simply register sources under that topic key;
agents are topic-agnostic and will pick it up automatically.
"""

from __future__ import annotations
import os
from typing import Dict, List, Optional


class JurisdictionRegistry:
    def __init__(self, base_path: Optional[str] = None):
        self._base_path = base_path or os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "data", "sample_sources"
        )
        # topic -> jurisdiction -> file path
        self._sources: Dict[str, Dict[str, str]] = {}
        self._load_defaults()

    def _load_defaults(self) -> None:
        defaults = {
            "basel_iii_capital_requirements": {
                "US": "us_basel_iii.json",
                "EU": "eu_basel_iii.json",
                "UK": "uk_basel_iii.json",
            }
        }
        for topic, jurisdictions in defaults.items():
            for jx, filename in jurisdictions.items():
                self.register_source(jx, topic, os.path.join(self._base_path, filename))

    def register_source(self, jurisdiction: str, topic: str, file_path: str) -> None:
        jurisdiction = jurisdiction.upper()
        self._sources.setdefault(topic, {})[jurisdiction] = file_path

    def get_source_path(self, jurisdiction: str, topic: str) -> Optional[str]:
        return self._sources.get(topic, {}).get(jurisdiction.upper())

    def list_jurisdictions(self, topic: str) -> List[str]:
        return list(self._sources.get(topic, {}).keys())

    def list_topics(self) -> List[str]:
        return list(self._sources.keys())

    def get_peer_jurisdictions(self, jurisdiction: str, topic: str) -> List[str]:
        """Return all other jurisdictions registered for a topic, used for
        cross-jurisdiction contradiction detection."""
        return [
            jx for jx in self.list_jurisdictions(topic)
            if jx.upper() != jurisdiction.upper()
        ]


# Singleton instance used across the application
registry = JurisdictionRegistry()
