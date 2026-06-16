"""
Canonical Output Schema
------------------------
Defines the strict, deterministic JSON contract every pipeline run must
produce. The schema is expressed in JSON Schema (Draft-07 compatible)
format so it can be validated with the standard `jsonschema` library in
any deployment environment.

A dependency-free fallback validator (`validate_with_fallback`) is
included so the validation layer degrades gracefully if `jsonschema`
is not installed — useful for air-gapped or minimal-dependency
deployments, and used automatically by the ValidationAgent.
"""

from __future__ import annotations
from typing import Any, Dict, List, Tuple

OUTPUT_JSON_SCHEMA: Dict[str, Any] = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "RegulatoryIntelligenceOutput",
    "type": "object",
    "required": [
        "jurisdiction",
        "regulation_topic",
        "summary",
        "key_rules",
        "contradictions",
        "confidence_score",
        "citations",
        "version",
        "timestamp",
        "audit_log_id",
    ],
    "additionalProperties": False,
    "properties": {
        "jurisdiction": {"type": "string", "minLength": 2},
        "regulation_topic": {"type": "string", "minLength": 2},
        "summary": {"type": "string", "minLength": 1},
        "key_rules": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["rule_key", "title", "value", "unit", "description"],
                "properties": {
                    "rule_key": {"type": "string"},
                    "title": {"type": "string"},
                    "value": {"type": "number"},
                    "unit": {"type": "string"},
                    "description": {"type": "string"},
                },
            },
        },
        "contradictions": {
            "type": "array",
            "items": {
                "type": "object",
                "required": [
                    "rule_key",
                    "jurisdiction_a",
                    "value_a",
                    "jurisdiction_b",
                    "value_b",
                    "severity",
                    "description",
                ],
                "properties": {
                    "rule_key": {"type": "string"},
                    "jurisdiction_a": {"type": "string"},
                    "value_a": {"type": "number"},
                    "jurisdiction_b": {"type": "string"},
                    "value_b": {"type": "number"},
                    "severity": {"type": "string", "enum": ["low", "medium", "high"]},
                    "description": {"type": "string"},
                },
            },
        },
        "confidence_score": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        "citations": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["source", "regulator", "publication_date", "reliability"],
                "properties": {
                    "source": {"type": "string"},
                    "regulator": {"type": "string"},
                    "publication_date": {"type": "string"},
                    "reliability": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                },
            },
        },
        "version": {"type": "string"},
        "timestamp": {"type": "string"},
        "audit_log_id": {"type": "string"},
    },
}


class SchemaValidationError(Exception):
    """Raised when an instance fails validation against OUTPUT_JSON_SCHEMA."""

    def __init__(self, errors: List[str]):
        self.errors = errors
        super().__init__(f"{len(errors)} schema validation error(s): {errors}")


def _validate_type(value: Any, expected: str) -> bool:
    type_map = {
        "string": str,
        "number": (int, float),
        "array": list,
        "object": dict,
        "boolean": bool,
    }
    py_type = type_map.get(expected)
    if py_type is None:
        return True
    if expected == "number" and isinstance(value, bool):
        return False
    return isinstance(value, py_type)


def _validate_node(instance: Any, schema: Dict[str, Any], path: str, errors: List[str]) -> None:
    if "type" in schema and not _validate_type(instance, schema["type"]):
        errors.append(f"{path}: expected type '{schema['type']}', got '{type(instance).__name__}'")
        return

    if schema.get("type") == "object" and isinstance(instance, dict):
        for required_field in schema.get("required", []):
            if required_field not in instance:
                errors.append(f"{path}: missing required field '{required_field}'")
        if schema.get("additionalProperties") is False:
            allowed = set(schema.get("properties", {}).keys())
            for key in instance.keys():
                if key not in allowed:
                    errors.append(f"{path}: unexpected additional field '{key}'")
        for prop_name, prop_schema in schema.get("properties", {}).items():
            if prop_name in instance:
                _validate_node(instance[prop_name], prop_schema, f"{path}.{prop_name}", errors)

    elif schema.get("type") == "array" and isinstance(instance, list):
        item_schema = schema.get("items")
        if item_schema:
            for idx, item in enumerate(instance):
                _validate_node(item, item_schema, f"{path}[{idx}]", errors)

    elif schema.get("type") == "string" and isinstance(instance, str):
        min_len = schema.get("minLength")
        if min_len is not None and len(instance) < min_len:
            errors.append(f"{path}: string shorter than minLength {min_len}")
        if "enum" in schema and instance not in schema["enum"]:
            errors.append(f"{path}: value '{instance}' not in allowed enum {schema['enum']}")

    elif schema.get("type") == "number" and isinstance(instance, (int, float)):
        minimum = schema.get("minimum")
        maximum = schema.get("maximum")
        if minimum is not None and instance < minimum:
            errors.append(f"{path}: value {instance} below minimum {minimum}")
        if maximum is not None and instance > maximum:
            errors.append(f"{path}: value {instance} above maximum {maximum}")


def validate_with_fallback(instance: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Validates `instance` against OUTPUT_JSON_SCHEMA.
    Prefers the standard `jsonschema` library if installed (full Draft-07
    compliance); otherwise falls back to the dependency-free engine above.
    Returns (is_valid, list_of_error_strings).
    """
    try:
        import jsonschema  # type: ignore

        validator = jsonschema.Draft7Validator(OUTPUT_JSON_SCHEMA)
        found_errors = sorted(validator.iter_errors(instance), key=lambda e: list(e.path))
        if not found_errors:
            return True, []
        return False, [f"{'.'.join(str(p) for p in e.path) or 'root'}: {e.message}" for e in found_errors]
    except ImportError:
        errors: List[str] = []
        _validate_node(instance, OUTPUT_JSON_SCHEMA, "root", errors)
        return (len(errors) == 0), errors
