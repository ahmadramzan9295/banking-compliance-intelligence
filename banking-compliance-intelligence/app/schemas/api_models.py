"""
Pydantic models for the FastAPI request/response layer.
Note: these mirror OUTPUT_JSON_SCHEMA for FastAPI's automatic OpenAPI docs
and request validation. The authoritative contract enforced by the
ValidationAgent remains OUTPUT_JSON_SCHEMA in output_schema.py.
"""

from pydantic import BaseModel, Field
from typing import List


class AnalyzeRequest(BaseModel):
    jurisdiction: str = Field(..., example="US", description="ISO-style jurisdiction code")
    regulation_topic: str = Field(..., example="basel_iii_capital_requirements")


class KeyRule(BaseModel):
    rule_key: str
    title: str
    value: float
    unit: str
    description: str


class Contradiction(BaseModel):
    rule_key: str
    jurisdiction_a: str
    value_a: float
    jurisdiction_b: str
    value_b: float
    severity: str
    description: str


class Citation(BaseModel):
    source: str
    regulator: str
    publication_date: str
    reliability: float


class AnalyzeResponse(BaseModel):
    jurisdiction: str
    regulation_topic: str
    summary: str
    key_rules: List[KeyRule]
    contradictions: List[Contradiction]
    confidence_score: float
    citations: List[Citation]
    version: str
    timestamp: str
    audit_log_id: str
