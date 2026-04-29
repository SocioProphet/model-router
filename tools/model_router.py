#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REQUEST_PATH = ROOT / "examples" / "route-request.example.json"
POLICY_PATH = ROOT / "examples" / "route-policy.example.json"

QUALITY = {"low": 0.25, "medium": 0.65, "high": 1.0}
COST = {"low": 1.0, "medium": 0.6, "high": 0.25}
LATENCY = {"low": 1.0, "medium": 0.6, "high": 0.25}
LOCALITY_LOCAL_FIRST = {"local": 1.0, "hosted": 0.35}
LOCALITY_STANDARD = {"local": 0.75, "hosted": 0.75}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def candidate_score(candidate: dict[str, Any], policy: dict[str, Any]) -> float:
    weights = policy["spec"]["scoreWeights"]
    locality_map = LOCALITY_LOCAL_FIRST if policy["spec"].get("preferLocal") else LOCALITY_STANDARD
    return round(
        (QUALITY[candidate["qualityTier"]] * weights["quality"])
        + (float(candidate["evalConfidence"]) * weights["evalConfidence"])
        + (locality_map[candidate["locality"]] * weights["locality"])
        + (COST[candidate["costTier"]] * weights["cost"])
        + (LATENCY[candidate["latencyTier"]] * weights["latency"]),
        6,
    )


def eligible(candidate: dict[str, Any], request: dict[str, Any], policy: dict[str, Any]) -> tuple[bool, list[str]]:
    spec = request["spec"]
    pspec = policy["spec"]
    reasons: list[str] = []
    if spec["task"] not in candidate["supportedTasks"]:
        return False, ["task-not-supported"]
    reasons.append("task-supported")
    if candidate["locality"] not in pspec["allowedLocalities"]:
        return False, ["locality-not-allowed"]
    if pspec.get("requiredGuardrailCompatibility") and not candidate.get("guardrailCompatible", False):
        return False, ["guardrail-incompatible"]
    reasons.append("guardrail-compatible")
    if float(candidate["evalConfidence"]) < float(pspec["minimumEvalConfidence"]):
        return False, ["eval-confidence-below-threshold"]
    reasons.append("eval-confidence-above-threshold")
    if pspec.get("privacyMode") == "local-first" and candidate["locality"] == "local":
        reasons.append("privacy-local-first")
        reasons.append("locality-preferred")
    elif pspec.get("privacyMode") == "local-first" and candidate["locality"] == "hosted":
        reasons.append("hosted-fallback-eligible")
    return True, reasons


def route(request: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    candidates = request["spec"]["candidates"]
    scored: list[tuple[float, dict[str, Any], list[str]]] = []
    blocked: list[str] = []
    for candidate in candidates:
        ok, reasons = eligible(candidate, request, policy)
        if ok:
            scored.append((candidate_score(candidate, policy), candidate, reasons))
        else:
            blocked.append(candidate["candidateRef"])
    if not scored:
        return build_decision(request, None, [], blocked, "blocked", ["no-eligible-candidates"])
    scored.sort(key=lambda item: (item[0], item[1]["locality"] == "local"), reverse=True)
    _, selected, reasons = scored[0]
    fallbacks = [candidate["candidateRef"] for _, candidate, _ in scored[1:]]
    return build_decision(request, selected, fallbacks, blocked, "selected", reasons)


def build_decision(
    request: dict[str, Any],
    selected: dict[str, Any] | None,
    fallbacks: list[str],
    blocked: list[str],
    status: str,
    reasons: list[str],
) -> dict[str, Any]:
    spec = request["spec"]
    decision_id = f"route-decision-{request['metadata']['requestId']}"
    return {
        "apiVersion": "modelrouter.socioprophet.dev/v1",
        "kind": "ModelRouteDecision",
        "metadata": {
            "decisionId": decision_id,
            "requestId": request["metadata"]["requestId"],
            "createdAt": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        },
        "spec": {
            "task": spec["task"],
            "privacyMode": spec["privacyMode"],
            "candidateRefs": [candidate["candidateRef"] for candidate in spec["candidates"]],
            "selectedCandidateRef": selected["candidateRef"] if selected else "",
            "decisionStatus": status,
            "reasonCodes": reasons,
            "policyRef": spec["policyRef"],
            "guardrailRef": spec["guardrailRef"],
            "evidenceRef": spec["evidenceRef"],
            "ledgerRef": spec["ledgerRef"],
            "fallbackRefs": fallbacks,
            "blockedCandidateRefs": blocked,
        },
    }


def emit_demo(output_path: Path | None = None) -> int:
    decision = route(load_json(REQUEST_PATH), load_json(POLICY_PATH))
    payload = json.dumps(decision, indent=2, sort_keys=True) + "\n"
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="SocioProphet governed model router")
    sub = parser.add_subparsers(dest="command", required=True)
    demo = sub.add_parser("emit-demo-decision")
    demo.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    if args.command == "emit-demo-decision":
        return emit_demo(args.output)
    raise AssertionError(args.command)


if __name__ == "__main__":
    raise SystemExit(main())
