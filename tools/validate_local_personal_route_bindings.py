#!/usr/bin/env python3
"""Validate LocalPersonalRouteBinding examples.

The validator keeps the router boundary explicit: local-first defaults,
consent for personalized routes, policy gate for hosted fallback, and evidence
for route decisions.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "schemas/local-personal-route-binding.schema.json"
EXAMPLES = sorted((ROOT / "examples").glob("local-personal-route-binding.*.json"))


class ValidationError(Exception):
    pass


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValidationError(f"missing file: {path.relative_to(ROOT)}") from exc
    except json.JSONDecodeError as exc:
        raise ValidationError(f"invalid JSON in {path.relative_to(ROOT)}: {exc}") from exc


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)


def validate_binding(path: Path, doc: dict[str, Any]) -> None:
    require(doc.get("schemaVersion") == "v0.1", f"{path}: schemaVersion must be v0.1")
    require(doc.get("kind") == "LocalPersonalRouteBinding", f"{path}: kind must be LocalPersonalRouteBinding")
    require(str(doc.get("bindingId", "")).startswith("urn:socioprophet:model-router-binding:"), f"{path}: invalid bindingId")
    require(str(doc.get("defaultLocalProfileRef", "")).startswith("urn:srcos:model-profile:"), f"{path}: defaultLocalProfileRef must reference SourceOS model carry")

    personalization = doc.get("personalization", {})
    if personalization.get("enabled"):
        require(personalization.get("governanceContractRef"), f"{path}: enabled personalization requires governanceContractRef")
        require(personalization.get("artifactRef"), f"{path}: enabled personalization requires artifactRef")
        require(personalization.get("activationRequiresLedgerApproval") is True, f"{path}: ledger approval is required")

    routes = doc.get("routes", [])
    require(routes, f"{path}: routes must be non-empty")
    for route in routes:
        if route.get("preferredTarget") == "personal-local":
            require(route.get("requiresConsent") is True, f"{path}: personal-local route requires consent")
        if route.get("preferredTarget") == "hosted" or route.get("fallbackTarget") == "hosted":
            require(route.get("requiresNetwork") is True, f"{path}: hosted route/fallback requires network flag")

    policy = doc.get("policy", {})
    require(policy.get("localFirst") is True, f"{path}: localFirst must be true")
    require(policy.get("promptEgressDefault") == "deny", f"{path}: prompt egress must deny by default")
    require(policy.get("hostedFallbackRequiresPolicy") is True, f"{path}: hosted fallback requires policy")
    require(policy.get("personalizationRequiresConsent") is True, f"{path}: personalization requires consent")
    require(policy.get("promptHashOnlyEvidence") is True, f"{path}: prompt evidence should be hash-only")

    evidence = doc.get("evidence", {})
    require(evidence.get("emitRouteDecision") is True, f"{path}: route decision evidence required")
    require(evidence.get("emitRuntimeHealth") is True, f"{path}: runtime health evidence required")
    require(evidence.get("emitGovernanceRefs") is True, f"{path}: governance refs evidence required")


def main() -> int:
    load_json(SCHEMA)
    if not EXAMPLES:
        print("ERR: no local personal route binding examples found", file=sys.stderr)
        return 2

    try:
        for example in EXAMPLES:
            doc = load_json(example)
            validate_binding(example.relative_to(ROOT), doc)
            print(f"ok: {example.relative_to(ROOT)}")
    except ValidationError as exc:
        print(f"ERR: {exc}", file=sys.stderr)
        return 1

    print("Local personal route binding validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
