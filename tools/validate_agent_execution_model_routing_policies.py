#!/usr/bin/env python3
"""Validate AgentExecutionModelRoutingPolicy examples.

The validator intentionally checks policy invariants that JSON Schema cannot
express cleanly without a heavyweight dependency. It enforces the operating
rule: high-end models make decisions; they do not perform routine chores.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "schemas/agent-execution-model-routing-policy.schema.json"
EXAMPLES = sorted((ROOT / "examples").glob("agent-execution-model-routing-policy.*.json"))

REQUIRED_TASK_CLASSES = {
    "formatting-rewrite",
    "log-triage",
    "routine-code",
    "architecture-decision",
    "hard-debugging",
    "security-review",
    "multi-repo-migration",
    "high-stakes-synthesis",
}

HIGH_END_REASONS = {
    "architecture-decision",
    "hard-debugging",
    "security-review",
    "privacy-review",
    "multi-repo-migration",
    "irreversible-production-decision",
    "high-stakes-synthesis",
    "conflicting-evidence-resolution",
    "repeated-standard-lane-failure",
    "release-gate-review",
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


def by_key(items: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in items:
        item_key = str(item.get(key, ""))
        require(item_key, f"item missing {key}")
        require(item_key not in result, f"duplicate {key}: {item_key}")
        result[item_key] = item
    return result


def validate_policy(path: Path, doc: dict[str, Any]) -> None:
    rel = path.relative_to(ROOT)
    require(doc.get("schemaVersion") == "v0.1", f"{rel}: schemaVersion must be v0.1")
    require(doc.get("kind") == "AgentExecutionModelRoutingPolicy", f"{rel}: invalid kind")
    require(str(doc.get("policyId", "")).startswith("urn:socioprophet:model-routing-policy:"), f"{rel}: invalid policyId")

    default_posture = doc.get("defaultPosture", {})
    require(default_posture.get("highEndDefault") == "deny", f"{rel}: highEndDefault must deny by default")
    require(default_posture.get("hostedFallback") == "policy-gated", f"{rel}: hosted fallback must be policy-gated")
    require(default_posture.get("localFirst") is True, f"{rel}: localFirst must be true")
    require(default_posture.get("failClosed") is True, f"{rel}: failClosed must be true")
    require(default_posture.get("mechanicalVerificationPreferred") is True, f"{rel}: mechanical verification must be preferred")

    lanes = by_key(doc.get("modelLanes", []), "laneId")
    for lane in ("no-model", "local-cheap", "cheap", "standard", "high-end"):
        require(lane in lanes, f"{rel}: missing required model lane {lane}")
    require(lanes["high-end"].get("requiresEscalationReceipt") is True, f"{rel}: high-end lane requires escalation receipt")
    if "pro" in lanes:
        require(lanes["pro"].get("requiresEscalationReceipt") is True, f"{rel}: pro lane requires escalation receipt")

    tasks = by_key(doc.get("taskClasses", []), "taskClass")
    missing_tasks = REQUIRED_TASK_CLASSES.difference(tasks)
    require(not missing_tasks, f"{rel}: missing required task classes: {sorted(missing_tasks)}")

    routine_lane = tasks["routine-code"].get("defaultLane")
    require(routine_lane in {"standard", "cheap", "local-cheap"}, f"{rel}: routine-code must not default to high-end")

    for chore in ("formatting-rewrite", "log-triage"):
        require(tasks[chore].get("defaultLane") in {"local-cheap", "cheap"}, f"{rel}: {chore} must default to cheap/local-cheap")
        require("high-end" not in tasks[chore].get("allowedEscalationLanes", []), f"{rel}: {chore} must not escalate directly to high-end")

    for high_risk in ("architecture-decision", "hard-debugging", "security-review", "multi-repo-migration", "high-stakes-synthesis"):
        require(tasks[high_risk].get("defaultLane") == "high-end", f"{rel}: {high_risk} must default to high-end")
        require(tasks[high_risk].get("requiresHumanJustification") is True, f"{rel}: {high_risk} requires justification")
        require(tasks[high_risk].get("requiresEvidence") is True, f"{rel}: {high_risk} requires evidence")

    stages = by_key(doc.get("chainStages", []), "stage")
    for stage in ("classification", "execution", "verification", "review"):
        require(stage in stages, f"{rel}: missing chain stage {stage}")
    require(stages["classification"].get("maxLaneWithoutEscalation") in {"local-cheap", "cheap"}, f"{rel}: classification cannot use high-end without escalation")
    require(stages["execution"].get("maxLaneWithoutEscalation") == "standard", f"{rel}: execution cannot use high-end without escalation")
    require(stages["verification"].get("defaultLane") == "no-model", f"{rel}: verification should default to no-model")
    require(stages["review"].get("maxLaneWithoutEscalation") == "high-end", f"{rel}: review may escalate to high-end with evidence")

    escalation = doc.get("escalationPolicy", {})
    reasons = set(escalation.get("allowedReasons", []))
    require(HIGH_END_REASONS.issubset(reasons), f"{rel}: incomplete high-end escalation reasons")
    require(escalation.get("requireReasonForHighEnd") is True, f"{rel}: high-end requires reason")
    require(escalation.get("requireReasonForPro") is True, f"{rel}: pro requires reason")
    require(escalation.get("deescalateAfterPlan") is True, f"{rel}: must de-escalate after plan")
    require(escalation.get("denyChattyThinkingOnHighEnd") is True, f"{rel}: high-end chatty thinking must be denied")

    context = doc.get("contextPolicy", {})
    require(context.get("clearOnTaskSwitch") is True, f"{rel}: clearOnTaskSwitch must be true")
    require(context.get("compactBeforeContextLimit") is True, f"{rel}: compactBeforeContextLimit must be true")
    require(context.get("preferPathReferences") is True, f"{rel}: prefer path references over large paste")
    require(context.get("trimLogsByDefault") is True, f"{rel}: trimLogsByDefault must be true")
    require(context.get("redactSecrets") is True, f"{rel}: redactSecrets must be true")
    require(context.get("disableNoncriticalConnectorsByDefault") is True, f"{rel}: noncritical connectors off by default")
    require(context.get("promptStorage") == "hash-only", f"{rel}: promptStorage should be hash-only")

    tools = doc.get("toolPolicy", {})
    require(tools.get("toolsOffUnlessNeeded") is True, f"{rel}: tools must be off unless needed")
    require(tools.get("networkToolsRequireReason") is True, f"{rel}: network tools require reason")
    require(tools.get("writeToolsRequireEvidence") is True, f"{rel}: write tools require evidence")
    require(tools.get("mechanicalVerificationRequired") is True, f"{rel}: mechanical verification required")

    evidence = doc.get("evidence", {})
    for key in ("emitRouteDecision", "emitEscalationReceipt", "emitCostClass", "emitContextPolicy", "emitToolPolicy", "promptHashOnly"):
        require(evidence.get(key) is True, f"{rel}: evidence.{key} must be true")
    ledger_refs = set(evidence.get("ledgerRefs", []))
    for repo in ("SocioProphet/model-governance-ledger", "SocioProphet/agentplane", "SocioProphet/guardrail-fabric"):
        require(repo in ledger_refs, f"{rel}: missing ledger/evidence ref {repo}")

    enforcement = doc.get("enforcement", {})
    require(enforcement.get("decisionAbi") == "sourceos.guardrail.decision.v0.1", f"{rel}: decision ABI mismatch")
    require(enforcement.get("onViolation") in {"deny", "defer", "quarantine"}, f"{rel}: invalid violation behavior")
    require(enforcement.get("denyHighEndWithoutReason") is True, f"{rel}: deny high-end without reason")
    require(enforcement.get("denyProWithoutReason") is True, f"{rel}: deny pro without reason")
    require(enforcement.get("downgradePreferred") is True, f"{rel}: downgradePreferred must be true")
    require(enforcement.get("routeDecisionRequiredBeforeExecution") is True, f"{rel}: route decision required before execution")


def main() -> int:
    load_json(SCHEMA)
    if not EXAMPLES:
        print("ERR: no agent execution model routing policy examples found", file=sys.stderr)
        return 2

    try:
        for example in EXAMPLES:
            doc = load_json(example)
            validate_policy(example, doc)
            print(f"ok: {example.relative_to(ROOT)}")
    except ValidationError as exc:
        print(f"ERR: {exc}", file=sys.stderr)
        return 1

    print("Agent execution model routing policy validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
