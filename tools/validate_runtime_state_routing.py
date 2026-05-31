#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = [
    ROOT / "examples" / "runtime-state-routing-policy.allocated.json",
    ROOT / "examples" / "runtime-state-routing-policy.failed.json",
]
STATES = {"runtime_allocated", "runtime_failed"}
AUTONOMY = {"report_only", "advisory", "human_review_required", "bounded_autonomy"}
LANES = {"no_model", "local_cheap", "cheap", "standard", "high_end", "pro"}


def load(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"expected object: {path}")
    return data


def validate(data: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    source = data.get("source", {})
    consequence = data.get("routing_consequence", {})
    state = source.get("runtime_state")
    evidence_refs = source.get("evidence_refs", [])
    receipt_refs = source.get("receipt_refs", [])
    blocking_gaps = source.get("blocking_gaps", [])
    failure_codes = source.get("failure_codes", [])
    must_preserve = consequence.get("must_preserve_warnings", [])

    if data.get("schema_version") != "1.0":
        problems.append("schema_version must be 1.0")
    if not str(data.get("policy_id", "")).startswith("runtime:state-routing-policy:"):
        problems.append("policy_id must be runtime state routing policy id")
    if data.get("owner", {}).get("plane") != "model-router":
        problems.append("owner.plane must be model-router")
    if data.get("owner", {}).get("repo") != "SocioProphet/model-router":
        problems.append("owner.repo must be SocioProphet/model-router")
    if source.get("state_authority") != "Sociosphere":
        problems.append("state_authority must be Sociosphere")
    if state not in STATES:
        problems.append("runtime_state is invalid")
    if not str(source.get("workspace_ref", "")).startswith("workspace://"):
        problems.append("workspace_ref must start with workspace://")
    if not str(source.get("environment_profile_id", "")).startswith("environment-sandbox:profile:"):
        problems.append("environment_profile_id must reference environment-sandbox profile")
    if not str(source.get("runtime_run_ref", "")).startswith("agentplane:runtime-sandbox-run:"):
        problems.append("runtime_run_ref must reference AgentPlane runtime sandbox run")
    if not str(source.get("environment_ref", "")).startswith("environment://"):
        problems.append("environment_ref must use environment://")
    if not isinstance(evidence_refs, list) or not evidence_refs:
        problems.append("evidence_refs must be a non-empty list")
    if not isinstance(receipt_refs, list) or not receipt_refs:
        problems.append("receipt_refs must be a non-empty list")
    if any(not str(ref).startswith("evidence://") for ref in evidence_refs):
        problems.append("all evidence refs must use evidence://")
    if any(not str(ref).startswith("receipt://") for ref in receipt_refs):
        problems.append("all receipt refs must use receipt://")
    if not isinstance(blocking_gaps, list):
        problems.append("blocking_gaps must be a list")
    if not isinstance(failure_codes, list):
        problems.append("failure_codes must be a list when present")
    if source.get("runtime_parity_certified") is not False:
        problems.append("runtime parity must not be certified in this tranche")

    if consequence.get("autonomy_ceiling") not in AUTONOMY:
        problems.append("autonomy_ceiling is invalid")
    if consequence.get("model_lane_ceiling") not in LANES:
        problems.append("model_lane_ceiling is invalid")
    if consequence.get("high_end_allowed") is not False:
        problems.append("high_end_allowed must remain false")
    if consequence.get("pro_allowed") is not False:
        problems.append("pro_allowed must remain false")
    if consequence.get("deterministic_verification_required") is not True:
        problems.append("deterministic verification must be required")
    if not isinstance(consequence.get("fallback_posture"), str) or not consequence.get("fallback_posture"):
        problems.append("fallback_posture must be present")
    if not isinstance(must_preserve, list):
        problems.append("must_preserve_warnings must be a list")
    if "runtime_parity_not_certified" not in must_preserve:
        problems.append("must preserve runtime_parity_not_certified warning")

    if state == "runtime_allocated":
        if "allocated" not in str(source.get("runtime_run_ref", "")):
            problems.append("runtime_allocated must reference allocated runtime run")
        if consequence.get("autonomy_ceiling") != "human_review_required":
            problems.append("runtime_allocated must require human review")
        if consequence.get("model_lane_ceiling") != "standard":
            problems.append("runtime_allocated must cap model lane at standard")
        for gap in ("teardown_not_complete", "leak_check_not_complete"):
            if gap not in blocking_gaps:
                problems.append(f"runtime_allocated must preserve blocking gap {gap}")
        if failure_codes:
            problems.append("runtime_allocated must not include failure codes")
    if state == "runtime_failed":
        if "failed" not in str(source.get("runtime_run_ref", "")):
            problems.append("runtime_failed must reference failed runtime run")
        if consequence.get("autonomy_ceiling") != "report_only":
            problems.append("runtime_failed must cap autonomy at report_only")
        if consequence.get("model_lane_ceiling") != "cheap":
            problems.append("runtime_failed must cap model lane at cheap")
        for gap in ("runtime_allocation_failed", "teardown_failed", "leak_check_failed"):
            if gap not in blocking_gaps:
                problems.append(f"runtime_failed must preserve blocking gap {gap}")
        if "runtime_allocation_failed" not in failure_codes:
            problems.append("runtime_failed must preserve runtime_allocation_failed failure code")
        if "runtime_validation_failed" not in must_preserve:
            problems.append("runtime_failed must preserve runtime_validation_failed warning")

    if not isinstance(data.get("non_claims"), list) or len(data.get("non_claims", [])) < 3:
        problems.append("non_claims must contain at least three entries")
    return problems


def main() -> int:
    failed = False
    results: dict[str, Any] = {}
    for path in FIXTURES:
        problems = validate(load(path))
        results[str(path.relative_to(ROOT))] = problems
        failed = failed or bool(problems)

    report = {
        "validator": "model-router.runtime-state-routing.validator.v1",
        "passed": not failed,
        "results": results,
        "non_claims": [
            "Validator does not certify runtime parity.",
            "Validator does not allocate infrastructure.",
            "Validator does not grant agent autonomy."
        ]
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    print(("PASS" if not failed else "FAIL") + ": runtime state routing fixtures")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
