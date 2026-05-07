#!/usr/bin/env python3
"""Validate Superconscious reasoning route examples.

This validator is dependency-free and read-only. It verifies that the Model Router
can return a deterministic no-provider route for Superconscious M1 reasoning runs
without prompt egress or model calls.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples" / "superconscious-reasoning-route.example.json"
VALID_TASK_CLASSES = {
    "reference-loop-demo",
    "tool-planner",
    "browser-operator",
    "terminal-operator",
    "office-assist",
    "memory-curator",
    "policy-explainer",
}


def fail(message: str) -> int:
    print(f"ERROR: {message}", file=sys.stderr)
    return 1


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate(doc: dict[str, Any]) -> int:
    if doc.get("apiVersion") != "modelrouter.socioprophet.dev/v1":
        return fail("apiVersion invalid")
    if doc.get("kind") != "SuperconsciousReasoningRoute":
        return fail("kind must be SuperconsciousReasoningRoute")
    spec = doc.get("spec") or {}
    for key in [
        "reasoningRunRef",
        "taskClass",
        "localFirst",
        "promptEgress",
        "privacyMode",
        "policyRef",
        "sourceosModelCarryRefs",
        "routeDecision",
    ]:
        if key not in spec:
            return fail(f"missing spec.{key}")
    if not str(spec["reasoningRunRef"]).startswith("urn:srcos:reasoning-run:"):
        return fail("reasoningRunRef must be a SourceOS reasoning-run URN")
    if spec["taskClass"] not in VALID_TASK_CLASSES:
        return fail("taskClass invalid")
    if spec["localFirst"] is not True:
        return fail("localFirst must be true for Superconscious M1")
    if spec["promptEgress"] != "denied":
        return fail("promptEgress must be denied for deterministic M1")
    if spec["privacyMode"] != "local-only":
        return fail("privacyMode must be local-only")
    if not isinstance(spec["sourceosModelCarryRefs"], list) or not spec["sourceosModelCarryRefs"]:
        return fail("sourceosModelCarryRefs must be a non-empty list")

    decision = spec["routeDecision"]
    for key in ["routeId", "decision", "providerClass", "modelCalls", "promptEgress", "evidenceRef"]:
        if key not in decision:
            return fail(f"missing spec.routeDecision.{key}")
    if decision["providerClass"] != "none":
        return fail("deterministic M1 providerClass must be none")
    if decision["modelCalls"] != "none":
        return fail("deterministic M1 modelCalls must be none")
    if decision["promptEgress"] != "denied":
        return fail("deterministic M1 decision promptEgress must be denied")
    print("OK: Superconscious reasoning route example validated")
    return 0


def main() -> int:
    return validate(load(FIXTURE))


if __name__ == "__main__":
    raise SystemExit(main())
