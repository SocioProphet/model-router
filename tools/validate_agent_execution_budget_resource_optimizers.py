#!/usr/bin/env python3
"""Validate AgentExecutionBudgetResourceOptimizer examples.

This validator checks the budget/resource optimization invariants that keep
model routing economically disciplined while preserving quality, safety, and
privacy constraints.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "schemas/agent-execution-budget-resource-optimizer.schema.json"
EXAMPLES = sorted((ROOT / "examples").glob("agent-execution-budget-resource-optimizer.*.json"))

REQUIRED_PREFERENCES = [
    "policy-compliance",
    "privacy",
    "safety",
    "quality-floor",
    "budget",
]

REQUIRED_SIGNALS = {
    "localModelProfileAvailable",
    "localServiceHealthy",
    "memoryAvailableBytes",
    "providerQuotaRemaining",
    "providerErrorRate",
    "providerLatencyP95Ms",
    "estimatedInputTokens",
    "estimatedOutputTokens",
}


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


def validate_optimizer(path: Path, doc: dict[str, Any]) -> None:
    rel = path.relative_to(ROOT)
    require(doc.get("schemaVersion") == "v0.1", f"{rel}: schemaVersion must be v0.1")
    require(doc.get("kind") == "AgentExecutionBudgetResourceOptimizer", f"{rel}: invalid kind")
    require(str(doc.get("optimizerId", "")).startswith("urn:socioprophet:model-routing-optimizer:"), f"{rel}: invalid optimizerId")
    require(str(doc.get("policyRef", "")).startswith("urn:socioprophet:model-routing-policy:"), f"{rel}: invalid policyRef")

    objective = doc.get("objective", {})
    require(objective.get("primary") == "minimize-cost-subject-to-quality-and-risk", f"{rel}: primary objective must minimize cost subject to quality and risk")
    preferences = objective.get("orderedPreferences", [])
    require(preferences[:5] == REQUIRED_PREFERENCES, f"{rel}: first preferences must be policy/privacy/safety/quality/budget in order")

    budget = doc.get("budgetPolicy", {})
    require(budget.get("onBudgetPressure") in {"downgrade", "defer", "deny", "require-human-approval"}, f"{rel}: invalid budget pressure response")
    require(budget.get("premiumReserveShare", 0) >= 0.2, f"{rel}: premium reserve share should preserve high-end capacity")
    windows = budget.get("windows", [])
    require(windows, f"{rel}: budget windows required")
    for window in windows:
        require(window.get("maxSpend", 0) >= 0, f"{rel}: maxSpend cannot be negative")
        require(window.get("highEndMaxShare", 1) <= 0.25, f"{rel}: high-end share too loose for {window.get('window')}")
        require(window.get("proMaxShare", 1) <= 0.05, f"{rel}: pro share too loose for {window.get('window')}")

    resource = doc.get("resourcePolicy", {})
    signals = set(resource.get("requiredSignals", []))
    missing = REQUIRED_SIGNALS.difference(signals)
    require(not missing, f"{rel}: missing required resource/quota signals: {sorted(missing)}")

    local = resource.get("localAdmission", {})
    require(local.get("preferWhenAvailable") is True, f"{rel}: local admission must prefer local when available")
    require(local.get("denyWhenThermalCritical") is True, f"{rel}: thermal critical must deny local admission")
    require(local.get("denyWhenBatteryCritical") is True, f"{rel}: battery critical must deny local admission")
    require(local.get("minMemoryAvailableBytes", 0) > 0, f"{rel}: local memory floor required")

    hosted = resource.get("hostedAdmission", {})
    require(hosted.get("requiresPolicy") is True, f"{rel}: hosted admission requires policy")
    require(hosted.get("requiresNetwork") is True, f"{rel}: hosted admission requires network")
    require(hosted.get("denyWhenQuotaUnknown") is True, f"{rel}: unknown quota must deny hosted/premium use")
    require(hosted.get("denyWhenProviderUnhealthy") is True, f"{rel}: unhealthy provider must deny hosted use")

    floors = {item.get("riskClass"): item for item in doc.get("qualityPolicy", {}).get("riskFloors", [])}
    for risk in ("low", "medium", "high", "critical"):
        require(risk in floors, f"{rel}: missing quality floor for {risk}")
    require(floors["low"].get("minimumLane") in {"no-model", "local-cheap", "cheap"}, f"{rel}: low risk floor too expensive")
    require(floors["medium"].get("minimumLane") == "standard", f"{rel}: medium risk should require standard")
    require(floors["high"].get("minimumLane") == "high-end", f"{rel}: high risk should require high-end")
    require(floors["critical"].get("minimumLane") == "pro", f"{rel}: critical risk should require pro")

    selection = doc.get("selectionPolicy", {})
    require(selection.get("candidateOrder", [])[:3] == ["no-model", "local-cheap", "cheap"], f"{rel}: candidate order must try cheap/no-model lanes first")
    require(selection.get("estimateBeforeRoute") is True, f"{rel}: estimator required before routing")
    require(selection.get("neverSilentlyUpgrade") is True, f"{rel}: never silently upgrade lanes")
    require("lower-cost" in selection.get("tieBreakers", []), f"{rel}: lower-cost tie breaker required")
    require("higher-quota-remaining" in selection.get("tieBreakers", []), f"{rel}: quota tie breaker required")

    evidence = doc.get("evidence", {})
    for key in ("emitBudgetDecision", "emitResourceSnapshot", "emitQuotaSnapshot", "emitCandidateSet", "emitSelectedCandidate", "promptHashOnly"):
        require(evidence.get(key) is True, f"{rel}: evidence.{key} must be true")

    enforcement = doc.get("enforcement", {})
    require(enforcement.get("decisionAbi") == "sourceos.guardrail.decision.v0.1", f"{rel}: decision ABI mismatch")
    require(enforcement.get("failClosedOnMissingSignals") is True, f"{rel}: missing signals must fail closed")
    require(enforcement.get("denyOnBudgetExhausted") is True, f"{rel}: exhausted budget must deny")
    require(enforcement.get("denyOnUnknownQuotaForPremium") is True, f"{rel}: unknown premium quota must deny")
    require(enforcement.get("routeBeforeExecution") is True, f"{rel}: route before execution required")


def main() -> int:
    load_json(SCHEMA)
    if not EXAMPLES:
        print("ERR: no agent execution budget/resource optimizer examples found", file=sys.stderr)
        return 2

    try:
        for example in EXAMPLES:
            doc = load_json(example)
            validate_optimizer(example, doc)
            print(f"ok: {example.relative_to(ROOT)}")
    except ValidationError as exc:
        print(f"ERR: {exc}", file=sys.stderr)
        return 1

    print("Agent execution budget/resource optimizer validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
