#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED_DECISION_FIELDS = {
    "task",
    "privacyMode",
    "candidateRefs",
    "selectedCandidateRef",
    "decisionStatus",
    "reasonCodes",
    "policyRef",
    "guardrailRef",
    "evidenceRef",
    "ledgerRef",
    "fallbackRefs",
}


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def fail(msg: str) -> int:
    print(f"ERROR: {msg}", file=sys.stderr)
    return 1


def validate_request(doc: dict) -> int:
    if doc.get("apiVersion") != "modelrouter.socioprophet.dev/v1":
        return fail("request apiVersion invalid")
    if doc.get("kind") != "ModelRouteRequest":
        return fail("request kind invalid")
    spec = doc.get("spec", {})
    for key in ["task", "privacyMode", "policyRef", "guardrailRef", "ledgerRef", "evidenceRef", "candidates"]:
        if key not in spec:
            return fail(f"request missing spec.{key}")
    if not spec["candidates"]:
        return fail("request candidates empty")
    return 0


def validate_policy(doc: dict) -> int:
    if doc.get("kind") != "ModelRoutePolicy":
        return fail("policy kind invalid")
    spec = doc.get("spec", {})
    for key in ["privacyMode", "minimumEvalConfidence", "allowedLocalities", "requiredGuardrailCompatibility", "scoreWeights"]:
        if key not in spec:
            return fail(f"policy missing spec.{key}")
    weights = spec["scoreWeights"]
    if round(sum(float(v) for v in weights.values()), 6) != 1.0:
        return fail("policy score weights must sum to 1.0")
    return 0


def validate_decision(doc: dict) -> int:
    if doc.get("kind") != "ModelRouteDecision":
        return fail("decision kind invalid")
    spec = doc.get("spec", {})
    missing = sorted(REQUIRED_DECISION_FIELDS - set(spec))
    if missing:
        return fail(f"decision missing fields: {missing}")
    if spec["decisionStatus"] not in {"selected", "blocked"}:
        return fail("decisionStatus invalid")
    if not isinstance(spec["candidateRefs"], list) or not spec["candidateRefs"]:
        return fail("candidateRefs must be non-empty list")
    if not isinstance(spec["fallbackRefs"], list):
        return fail("fallbackRefs must be list")
    if not isinstance(spec["reasonCodes"], list) or not spec["reasonCodes"]:
        return fail("reasonCodes must be non-empty list")
    return 0


def main() -> int:
    checks = [
        validate_request(load(ROOT / "examples" / "route-request.example.json")),
        validate_policy(load(ROOT / "examples" / "route-policy.example.json")),
        validate_decision(load(ROOT / "examples" / "route-decision.example.json")),
    ]
    if any(checks):
        return 1
    print("OK: route examples validated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
