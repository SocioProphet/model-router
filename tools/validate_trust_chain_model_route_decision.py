#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "schemas" / "trust-chain-model-route-decision.v0.1.schema.json"
ALLOW_FIXTURE = ROOT / "examples" / "trust-chain-model-route-decision.allow.json"
FALLBACK_FIXTURE = ROOT / "examples" / "trust-chain-model-route-decision.fallback.json"
DENY_FIXTURE = ROOT / "examples" / "trust-chain-model-route-decision.deny.json"

REQUIRED_ROUTE_REFS = {
    "model_factsheet_ref",
    "eval_receipt_ref",
    "runtime_or_provider_admission_ref",
    "policy_profile_ref",
    "guardrail_decision_ref",
}


class ValidationError(Exception):
    pass


def fail(message: str) -> None:
    raise ValidationError(message)


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValidationError(f"missing file: {path.relative_to(ROOT)}") from exc
    except json.JSONDecodeError as exc:
        raise ValidationError(f"invalid JSON in {path.relative_to(ROOT)}: {exc}") from exc


def json_type_name(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int) and not isinstance(value, bool):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return type(value).__name__


def type_matches(value: Any, expected: str) -> bool:
    actual = json_type_name(value)
    if expected == "number":
        return actual in {"integer", "number"}
    return actual == expected


def validate_schema(schema: dict[str, Any], value: Any, path: str = "$") -> None:
    if "const" in schema and value != schema["const"]:
        fail(f"{path}: expected const {schema['const']!r}, got {value!r}")
    if "enum" in schema and value not in schema["enum"]:
        fail(f"{path}: {value!r} not in enum {schema['enum']!r}")
    expected_type = schema.get("type")
    if expected_type is not None:
        expected_types = expected_type if isinstance(expected_type, list) else [expected_type]
        if not any(type_matches(value, item) for item in expected_types):
            fail(f"{path}: expected type {expected_types!r}, got {json_type_name(value)!r}")
    if isinstance(value, dict):
        required = schema.get("required", [])
        for key in required:
            if key not in value:
                fail(f"{path}: missing required property {key!r}")
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            extra = sorted(set(value) - set(properties))
            if extra:
                fail(f"{path}: unexpected properties {extra!r}")
        additional = schema.get("additionalProperties")
        for key, item in value.items():
            child_schema = properties.get(key)
            if child_schema is None and isinstance(additional, dict):
                child_schema = additional
            if child_schema is not None:
                validate_schema(child_schema, item, f"{path}.{key}")
    if isinstance(value, list):
        item_schema = schema.get("items")
        if item_schema is not None:
            for index, item in enumerate(value):
                validate_schema(item_schema, item, f"{path}[{index}]")


def route_by_ref(record: dict[str, Any], route_ref: str | None) -> dict[str, Any] | None:
    if route_ref is None:
        return None
    for route in record.get("candidate_routes", []):
        if route.get("route_ref") == route_ref:
            return route
    return None


def route_has_required_refs(route: dict[str, Any]) -> bool:
    refs = route.get("trust_chain_refs", {})
    return all(bool(refs.get(key)) for key in REQUIRED_ROUTE_REFS)


def validate_allow(record: dict[str, Any], path: Path) -> None:
    if record.get("decision") != "allow":
        fail(f"{path}: allow fixture requires decision=allow")
    route = route_by_ref(record, record.get("selected_route"))
    if route is None:
        fail(f"{path}: selected_route must match a candidate route")
    if not route_has_required_refs(route):
        fail(f"{path}: allowed route requires all Trust Chain refs")
    effects = record.get("effects", {})
    if effects.get("route_allowed") is not True:
        fail(f"{path}: allow fixture must allow route")
    if effects.get("prompt_egress_allowed") is not False:
        fail(f"{path}: local allow fixture must keep prompt egress denied")
    if effects.get("human_review_required") is not False:
        fail(f"{path}: allow fixture must not require human review")


def validate_fallback(record: dict[str, Any], path: Path) -> None:
    if record.get("decision") != "fallback":
        fail(f"{path}: fallback fixture requires decision=fallback")
    route = route_by_ref(record, record.get("selected_route"))
    if route is None:
        fail(f"{path}: selected_route must match a candidate route")
    if not route_has_required_refs(route):
        fail(f"{path}: fallback selected route requires all Trust Chain refs")
    first = record.get("candidate_routes", [{}])[0]
    if route_has_required_refs(first):
        fail(f"{path}: preferred route should be incomplete to justify fallback")
    effects = record.get("effects", {})
    if effects.get("fallback_required") is not True:
        fail(f"{path}: fallback fixture must require fallback")
    if effects.get("prompt_egress_allowed") is not False:
        fail(f"{path}: fallback fixture must deny prompt egress")


def validate_deny(record: dict[str, Any], path: Path) -> None:
    if record.get("decision") != "deny":
        fail(f"{path}: deny fixture requires decision=deny")
    if record.get("selected_route") is not None:
        fail(f"{path}: deny fixture must not select a route")
    effects = record.get("effects", {})
    if effects.get("route_allowed") is not False:
        fail(f"{path}: deny fixture must deny route")
    if effects.get("human_review_required") is not True:
        fail(f"{path}: deny fixture must require human review")
    for route in record.get("candidate_routes", []):
        if route_has_required_refs(route):
            fail(f"{path}: deny fixture must not include a complete candidate route")
    remediation = record.get("remediation", [])
    if not isinstance(remediation, list) or not remediation:
        fail(f"{path}: deny fixture requires remediation")
    for item in remediation:
        if item.get("required_before_route") is not True:
            fail(f"{path}: remediation must be required before route")
        if not item.get("authority"):
            fail(f"{path}: remediation requires authority")


def validate_record(path: Path) -> None:
    schema = load_json(SCHEMA)
    record = load_json(path)
    validate_schema(schema, record)
    decision = record.get("decision")
    if decision == "allow":
        validate_allow(record, path)
    elif decision == "fallback":
        validate_fallback(record, path)
    elif decision == "deny":
        validate_deny(record, path)


def main() -> int:
    try:
        for path in (ALLOW_FIXTURE, FALLBACK_FIXTURE, DENY_FIXTURE):
            validate_record(path)
    except ValidationError as exc:
        print(f"ERR: {exc}", file=sys.stderr)
        return 2
    print("OK: Trust Chain model route decisions passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
