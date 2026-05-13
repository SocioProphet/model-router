#!/usr/bin/env python3
"""Emit an agent execution model-route decision.

This executable slice combines two contracts:

- AgentExecutionModelRoutingPolicy: which lanes are allowed.
- AgentExecutionBudgetResourceOptimizer: which allowed lane is optimal now.

The router chooses the cheapest feasible lane that satisfies policy, quality,
budget, resource, quota, and provider-health constraints. It never silently
upgrades to a more expensive lane.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_POLICY = ROOT / "examples/agent-execution-model-routing-policy.default.json"
DEFAULT_OPTIMIZER = ROOT / "examples/agent-execution-budget-resource-optimizer.default.json"

LANE_RANK = {
    "no-model": 0,
    "local-cheap": 1,
    "cheap": 2,
    "standard": 3,
    "high-end": 4,
    "pro": 5,
}

LANE_COST_CLASS = {
    "no-model": "none",
    "local-cheap": "low",
    "cheap": "low",
    "standard": "medium",
    "high-end": "high",
    "pro": "maximum",
}

DEFAULT_COST_ESTIMATE = {
    "no-model": 0.0,
    "local-cheap": 0.001,
    "cheap": 0.02,
    "standard": 0.15,
    "high-end": 1.0,
    "pro": 2.0,
}

REQUIRED_RESOURCE_SIGNALS = [
    "localModelProfileAvailable",
    "localServiceHealthy",
    "batteryState",
    "thermalState",
    "memoryAvailableBytes",
    "networkAvailable",
    "providerQuotaKnown",
    "providerQuotaRemainingShare",
    "providerErrorRate",
    "providerLatencyP95Ms",
    "estimatedInputTokens",
    "estimatedOutputTokens",
]


class RouteDecisionError(Exception):
    """Raised for invalid route-decision input."""


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RouteDecisionError(f"missing JSON file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise RouteDecisionError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise RouteDecisionError(f"JSON document must be object: {path}")
    return value


def by_key(items: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in items:
        item_key = str(item.get(key, ""))
        if item_key:
            result[item_key] = item
    return result


def lane_at_least(lane: str, minimum: str) -> bool:
    return LANE_RANK[lane] >= LANE_RANK[minimum]


def lane_at_most(lane: str, maximum: str) -> bool:
    return LANE_RANK[lane] <= LANE_RANK[maximum]


def require_resource_signals(resources: dict[str, Any], optimizer: dict[str, Any]) -> None:
    required = set(REQUIRED_RESOURCE_SIGNALS)
    required.update(optimizer.get("resourcePolicy", {}).get("requiredSignals", []))
    missing = sorted(key for key in required if key not in resources)
    if missing:
        raise RouteDecisionError(f"missing resource signals: {', '.join(missing)}")


def risk_floor(optimizer: dict[str, Any], risk_class: str) -> dict[str, Any]:
    floors = by_key(optimizer.get("qualityPolicy", {}).get("riskFloors", []), "riskClass")
    try:
        return floors[risk_class]
    except KeyError as exc:
        raise RouteDecisionError(f"unknown riskClass: {risk_class}") from exc


def task_policy(policy: dict[str, Any], task_class: str) -> dict[str, Any]:
    tasks = by_key(policy.get("taskClasses", []), "taskClass")
    try:
        return tasks[task_class]
    except KeyError as exc:
        raise RouteDecisionError(f"unknown taskClass: {task_class}") from exc


def stage_policy(policy: dict[str, Any], stage: str) -> dict[str, Any]:
    stages = by_key(policy.get("chainStages", []), "stage")
    try:
        return stages[stage]
    except KeyError as exc:
        raise RouteDecisionError(f"unknown stage: {stage}") from exc


def lane_cost(policy: dict[str, Any], lane: str, resources: dict[str, Any]) -> float:
    override = resources.get("estimatedLaneCosts", {})
    if isinstance(override, dict) and lane in override:
        return float(override[lane])
    tokens = float(resources.get("estimatedInputTokens", 0)) + float(resources.get("estimatedOutputTokens", 0))
    base = DEFAULT_COST_ESTIMATE[lane]
    if lane in {"cheap", "standard", "high-end", "pro"} and tokens > 0:
        # Conservative placeholder until provider-specific price tables land.
        multiplier = {"cheap": 0.0000002, "standard": 0.000001, "high-end": 0.000006, "pro": 0.000012}[lane]
        return round(max(base, tokens * multiplier), 6)
    return base


def budget_window(optimizer: dict[str, Any], window_name: str) -> dict[str, Any]:
    windows = by_key(optimizer.get("budgetPolicy", {}).get("windows", []), "window")
    try:
        return windows[window_name]
    except KeyError as exc:
        raise RouteDecisionError(f"unknown budgetWindow: {window_name}") from exc


def lane_feasibility(
    *,
    lane: str,
    policy: dict[str, Any],
    optimizer: dict[str, Any],
    task: dict[str, Any],
    stage: dict[str, Any],
    quality_floor: dict[str, Any],
    resources: dict[str, Any],
    requested_lane: str | None,
    escalation_reason: str | None,
    budget_remaining: float,
    budget_window_doc: dict[str, Any],
) -> dict[str, Any]:
    reasons: list[str] = []
    feasible = True

    minimum_lane = str(quality_floor["minimumLane"])
    if not lane_at_least(lane, minimum_lane):
        feasible = False
        reasons.append(f"below-quality-floor:{minimum_lane}")

    max_stage_lane = str(stage["maxLaneWithoutEscalation"])
    if not escalation_reason and not lane_at_most(lane, max_stage_lane):
        feasible = False
        reasons.append(f"stage-max-without-escalation:{max_stage_lane}")

    task_default = str(task["defaultLane"])
    allowed_task_lanes = {task_default, *task.get("allowedEscalationLanes", [])}
    if lane not in allowed_task_lanes and lane != stage.get("defaultLane"):
        feasible = False
        reasons.append("not-allowed-for-task-class")

    allowed_reasons = set(policy.get("escalationPolicy", {}).get("allowedReasons", []))
    if lane in {"high-end", "pro"}:
        if not escalation_reason:
            feasible = False
            reasons.append("premium-lane-requires-escalation-reason")
        elif escalation_reason not in allowed_reasons:
            feasible = False
            reasons.append("invalid-escalation-reason")

    local = optimizer.get("resourcePolicy", {}).get("localAdmission", {})
    if lane == "local-cheap":
        if not resources.get("localModelProfileAvailable"):
            feasible = False
            reasons.append("local-model-profile-unavailable")
        if not resources.get("localServiceHealthy"):
            feasible = False
            reasons.append("local-service-unhealthy")
        if local.get("denyWhenThermalCritical") and resources.get("thermalState") == "critical":
            feasible = False
            reasons.append("thermal-critical")
        if local.get("denyWhenBatteryCritical") and resources.get("batteryState") == "critical":
            feasible = False
            reasons.append("battery-critical")
        if int(resources.get("memoryAvailableBytes", 0)) < int(local.get("minMemoryAvailableBytes", 0)):
            feasible = False
            reasons.append("insufficient-local-memory")

    hosted = optimizer.get("resourcePolicy", {}).get("hostedAdmission", {})
    if lane in {"cheap", "standard", "high-end", "pro"}:
        if hosted.get("requiresNetwork") and not resources.get("networkAvailable"):
            feasible = False
            reasons.append("network-unavailable")
        if hosted.get("denyWhenQuotaUnknown") and not resources.get("providerQuotaKnown"):
            feasible = False
            reasons.append("provider-quota-unknown")
        if hosted.get("denyWhenProviderUnhealthy") and float(resources.get("providerErrorRate", 1.0)) > float(hosted.get("maxProviderErrorRate", 1.0)):
            feasible = False
            reasons.append("provider-error-rate-too-high")
        if int(resources.get("providerLatencyP95Ms", 999999999)) > int(hosted.get("maxProviderLatencyP95Ms", 999999999)):
            feasible = False
            reasons.append("provider-latency-too-high")

    if lane in {"high-end", "pro"}:
        remaining_share = float(resources.get("providerQuotaRemainingShare", -1.0))
        if remaining_share < 0:
            feasible = False
            reasons.append("provider-quota-share-missing")
        if remaining_share < float(optimizer.get("budgetPolicy", {}).get("premiumReserveShare", 0.0)):
            feasible = False
            reasons.append("premium-reserve-below-threshold")

    cost = lane_cost(policy, lane, resources)
    if cost > budget_remaining:
        feasible = False
        reasons.append("budget-insufficient")

    if lane == "high-end" and budget_window_doc.get("highEndMaxShare", 1.0) <= 0:
        feasible = False
        reasons.append("high-end-share-zero")
    if lane == "pro" and budget_window_doc.get("proMaxShare", 1.0) <= 0:
        feasible = False
        reasons.append("pro-share-zero")

    if feasible:
        reasons.append("feasible")

    return {
        "lane": lane,
        "feasible": feasible,
        "estimatedCost": cost,
        "reasons": reasons,
    }


def decision_id(payload: dict[str, Any]) -> str:
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()[:24]
    return f"urn:socioprophet:model-route-decision:{digest}"


def make_decision(
    *,
    policy: dict[str, Any],
    optimizer: dict[str, Any],
    resources: dict[str, Any],
    task_class: str,
    stage_name: str,
    risk_class: str,
    requested_lane: str | None,
    escalation_reason: str | None,
    budget_window_name: str,
    budget_remaining: float,
) -> dict[str, Any]:
    require_resource_signals(resources, optimizer)

    task = task_policy(policy, task_class)
    stage = stage_policy(policy, stage_name)
    floor = risk_floor(optimizer, risk_class)
    window = budget_window(optimizer, budget_window_name)

    candidate_order = optimizer.get("selectionPolicy", {}).get("candidateOrder", [])
    if not candidate_order:
        raise RouteDecisionError("optimizer candidateOrder is empty")

    candidates = [
        lane_feasibility(
            lane=lane,
            policy=policy,
            optimizer=optimizer,
            task=task,
            stage=stage,
            quality_floor=floor,
            resources=resources,
            requested_lane=requested_lane,
            escalation_reason=escalation_reason,
            budget_remaining=budget_remaining,
            budget_window_doc=window,
        )
        for lane in candidate_order
    ]

    requested_evaluation = None
    if requested_lane:
        if requested_lane not in LANE_RANK:
            raise RouteDecisionError(f"unknown requestedLane: {requested_lane}")
        requested_evaluation = lane_feasibility(
            lane=requested_lane,
            policy=policy,
            optimizer=optimizer,
            task=task,
            stage=stage,
            quality_floor=floor,
            resources=resources,
            requested_lane=requested_lane,
            escalation_reason=escalation_reason,
            budget_remaining=budget_remaining,
            budget_window_doc=window,
        )

    feasible_candidates = [candidate for candidate in candidates if candidate["feasible"]]
    if not feasible_candidates:
        status = "deferred"
        selected_lane = None
        reason = "no-feasible-candidate"
        selected_cost = None
        cost_class = None
    else:
        selected = feasible_candidates[0]
        selected_lane = str(selected["lane"])
        selected_cost = float(selected["estimatedCost"])
        cost_class = LANE_COST_CLASS[selected_lane]
        if requested_lane and selected_lane != requested_lane:
            status = "downgraded" if LANE_RANK[selected_lane] < LANE_RANK[requested_lane] else "selected"
            reason = f"requested-lane-not-optimal-or-feasible:{requested_lane}"
        else:
            status = "selected"
            reason = "cheapest-feasible-candidate"

    payload = {
        "schemaVersion": "v0.1",
        "kind": "AgentExecutionRouteDecision",
        "createdAt": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "policyRef": policy.get("policyId"),
        "optimizerRef": optimizer.get("optimizerId"),
        "input": {
            "taskClass": task_class,
            "stage": stage_name,
            "riskClass": risk_class,
            "requestedLane": requested_lane,
            "escalationReason": escalation_reason,
            "budgetWindow": budget_window_name,
            "budgetRemaining": budget_remaining,
        },
        "selected": {
            "lane": selected_lane,
            "status": status,
            "reason": reason,
            "costClass": cost_class,
            "estimatedCost": selected_cost,
        },
        "quality": {
            "minimumLane": floor["minimumLane"],
            "requiresVerification": bool(floor["requiresVerification"]),
        },
        "budget": {
            "window": budget_window_name,
            "remaining": budget_remaining,
            "onBudgetPressure": optimizer.get("budgetPolicy", {}).get("onBudgetPressure"),
            "premiumReserveShare": optimizer.get("budgetPolicy", {}).get("premiumReserveShare"),
        },
        "resources": {key: resources[key] for key in sorted(resources) if key != "estimatedLaneCosts"},
        "requestedEvaluation": requested_evaluation,
        "candidateSet": candidates,
        "evidence": {
            "emitRouteDecision": True,
            "emitBudgetDecision": optimizer.get("evidence", {}).get("emitBudgetDecision") is True,
            "emitResourceSnapshot": optimizer.get("evidence", {}).get("emitResourceSnapshot") is True,
            "emitQuotaSnapshot": optimizer.get("evidence", {}).get("emitQuotaSnapshot") is True,
            "emitCandidateSet": optimizer.get("evidence", {}).get("emitCandidateSet") is True,
            "emitSelectedCandidate": optimizer.get("evidence", {}).get("emitSelectedCandidate") is True,
            "promptEvidenceMode": "hash-only",
            "decisionAbi": optimizer.get("enforcement", {}).get("decisionAbi", "sourceos.guardrail.decision.v0.1"),
        },
    }
    payload["decisionId"] = decision_id(payload)
    return payload


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Emit an AgentExecutionRouteDecision JSON document.")
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    parser.add_argument("--optimizer", type=Path, default=DEFAULT_OPTIMIZER)
    parser.add_argument("--resources", type=Path, required=True)
    parser.add_argument("--task-class", required=True)
    parser.add_argument("--stage", required=True)
    parser.add_argument("--risk-class", choices=["low", "medium", "high", "critical"], default="medium")
    parser.add_argument("--requested-lane", choices=list(LANE_RANK), default=None)
    parser.add_argument("--escalation-reason", default=None)
    parser.add_argument("--budget-window", default="task")
    parser.add_argument("--budget-remaining", type=float, default=2.0)
    parser.add_argument("--compact", action="store_true", help="Emit compact JSON")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        decision = make_decision(
            policy=load_json(args.policy),
            optimizer=load_json(args.optimizer),
            resources=load_json(args.resources),
            task_class=args.task_class,
            stage_name=args.stage,
            risk_class=args.risk_class,
            requested_lane=args.requested_lane,
            escalation_reason=args.escalation_reason,
            budget_window_name=args.budget_window,
            budget_remaining=args.budget_remaining,
        )
    except RouteDecisionError as exc:
        print(f"ERR: {exc}", file=sys.stderr)
        return 2

    if args.compact:
        print(json.dumps(decision, sort_keys=True, separators=(",", ":")))
    else:
        print(json.dumps(decision, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
