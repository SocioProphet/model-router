#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REQUEST_PATH = ROOT / "examples" / "route-request.example.json"
POLICY_PATH = ROOT / "examples" / "route-policy.example.json"

# Runtime authorization source of truth. This is the SAME contract the CI
# conformance gate (validate_model_route_authorization.py) reads. Wiring it here
# turns the invariant model_availability_is_not_authorization from a CI-only
# check into a runtime control: an unledgered model is denied at route time.
AUTHORIZATION_PATH = ROOT / "contracts/prophet-mesh/model-route-authorization.v0.1.json"

# Import the canonical fail-closed decision -- single source of truth for the
# deny logic, shared with the CI gate. Make the sibling tools/ dir importable
# regardless of how this module is loaded (script, importlib, or pytest).
sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate_model_route_authorization import (  # noqa: E402
    INVARIANT,
    is_route_authorized,
)

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


def resolve_governance_route(candidate: dict[str, Any]) -> str | None:
    """The governance route id a candidate maps to in the authorization mirror.

    A candidate that does not even declare which governed model it is cannot be
    authorized -- that is a fail-closed condition, not a default-allow.
    """
    route = candidate.get("governanceRoute")
    if isinstance(route, str) and route.strip():
        return route.strip()
    return None


def authorize(candidate: dict[str, Any], authorization: dict[str, Any]) -> tuple[bool, str]:
    """Runtime fail-closed authorization for a single candidate.

    Denies unless the candidate's governance route carries an evidence-backed
    ``authorized`` record in the Model Governance Ledger mirror. Availability in
    the routing surface never implies authorization.
    """
    route = resolve_governance_route(candidate)
    if route is None:
        return False, "unauthorized-no-governance-route"
    if not is_route_authorized(route, authorization):
        return False, "unauthorized-unledgered-model"
    return True, "authorized"


def resolve_authorization(
    request: dict[str, Any], authorization: dict[str, Any] | None
) -> tuple[dict[str, Any], str]:
    """Resolve the runtime authorization mirror + a provenance ref.

    Precedence: explicit ``authorization`` arg (callers/tests) > request
    ``spec.authorizationRef`` > the canonical prophet-mesh authorization
    contract. The final fallback is the production source of truth, so a caller
    that supplies nothing still gets fail-closed enforcement.
    """
    ref = request.get("spec", {}).get("authorizationRef")
    if authorization is not None:
        return authorization, ref or "inline"
    if ref:
        path = Path(ref)
        if not path.is_absolute():
            path = ROOT / ref
        return load_json(path), ref
    return load_json(AUTHORIZATION_PATH), str(AUTHORIZATION_PATH.relative_to(ROOT))


def route(
    request: dict[str, Any],
    policy: dict[str, Any],
    authorization: dict[str, Any] | None = None,
) -> dict[str, Any]:
    authorization, authorization_ref = resolve_authorization(request, authorization)
    candidates = request["spec"]["candidates"]
    scored: list[tuple[float, dict[str, Any], list[str]]] = []
    blocked: list[str] = []
    authorized_seen = False
    for candidate in candidates:
        # Authorization is enforced BEFORE eligibility/scoring, so an
        # unauthorized model can never be scored, selected, or dispatched.
        ok_auth, auth_reason = authorize(candidate, authorization)
        if not ok_auth:
            blocked.append(candidate["candidateRef"])
            continue
        authorized_seen = True
        ok, reasons = eligible(candidate, request, policy)
        if ok:
            scored.append((candidate_score(candidate, policy), candidate, ["authorized", *reasons]))
        else:
            blocked.append(candidate["candidateRef"])
    if not scored:
        block_reason = (
            ["no-eligible-candidates"]
            if authorized_seen
            else ["no-authorized-candidates", "unauthorized-unledgered-model"]
        )
        return build_decision(request, None, [], blocked, "blocked", block_reason, authorization_ref)
    scored.sort(key=lambda item: (item[0], item[1]["locality"] == "local"), reverse=True)
    _, selected, reasons = scored[0]
    # Control that cannot silently pass: re-assert authorization on the exact
    # model about to be dispatched. If this ever fires, the gate was bypassed.
    selected_route = resolve_governance_route(selected)
    if not selected_route or not is_route_authorized(selected_route, authorization):
        raise RuntimeError(
            f"fail-closed: selected route '{selected_route}' is not authorized ({INVARIANT})"
        )
    fallbacks = [candidate["candidateRef"] for _, candidate, _ in scored[1:]]
    return build_decision(request, selected, fallbacks, blocked, "selected", reasons, authorization_ref)


def build_decision(
    request: dict[str, Any],
    selected: dict[str, Any] | None,
    fallbacks: list[str],
    blocked: list[str],
    status: str,
    reasons: list[str],
    authorization_ref: str = "",
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
            "authorizationRef": authorization_ref,
            "selectedGovernanceRoute": resolve_governance_route(selected) if selected else "",
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
