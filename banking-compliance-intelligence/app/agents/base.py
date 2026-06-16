"""
Base Agent
----------
Every agent implements `run(context: dict) -> dict`, consuming and
returning a shared pipeline context. This keeps the orchestrator simple
and makes agents independently testable and replaceable — the core
requirement for an extensible, modular multi-agent architecture.
"""

from __future__ import annotations
import time
from abc import ABC, abstractmethod
from typing import Any, Dict

from app.utils.logging_config import get_logger


class BaseAgent(ABC):
    name: str = "base_agent"

    def __init__(self):
        self.logger = get_logger(f"agent.{self.name}")

    @abstractmethod
    def process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Implement agent-specific logic. Must return the updated context."""
        raise NotImplementedError

    def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        start = time.perf_counter()
        self.logger.info(f"stage_start agent='{self.name}'")
        try:
            updated_context = self.process(context)
        except Exception as exc:
            self.logger.error(f"stage_failed agent='{self.name}' error='{exc}'")
            raise
        duration_ms = (time.perf_counter() - start) * 1000
        self.logger.info(f"stage_complete agent='{self.name}' duration_ms={duration_ms:.3f}")
        updated_context.setdefault("_stage_timings", []).append(
            {"stage": self.name, "duration_ms": round(duration_ms, 3)}
        )
        return updated_context
