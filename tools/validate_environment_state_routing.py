#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = [
    ROOT / "examples" / "environment-state-routing-policy.observed.json",
    ROOT / "examples" / "environment-state-routing-policy.failed.json",
]
STATES = {"environment_observed", "environment_failed"}
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
    state = source.get("environment_state")
    evidence_refs = source.get("evidence_refs", [])
    receipt_refs = source.get("receipt_refs", [])
    warning_codes = source.get("warning_codes", [])
    failure_codes = source.get("failure_codes", [])
    must_preserve = consequence.get("must_preserve_warnings", [])

    if data.get("schema_version") != "1.0":
        problems.append("schema_version must be 1.0")
    if not str(data.get("policy_id", "")).startswith("environment:state-routing-policy:"):
        problems.append("policy_id must be environment state routing policy id")
    if data.get("owner", {}).get("plane") != "model-router":
        problems.append("owner.plane must be model-router")
    if data.get("owner", {}).get("repo") != "SocioProphet/model-router":
        problems.append("owner.repo must be SocioProphet/model-router")
    if source.get("state_authority") != "Sociosphere":
        problems.append("state_authority must be Sociosphere")
    if state not in STATES:
        problems.append("environment_state is invalid")
    if not str(source.get("workspace_ref", "")).startswith("workspace://"):
        problems.append("workspace_ref must start with workspace://")
    if not str(source.get("environment_profile_id", "")).startswith("environment-sandbox:profile:"):
        problems.append("environment_profile_id must reference environment-sandbox profile")
    if not str(source.get("prophet_platform_response_ref", "")).startswith("environment:validate-change-v2-response:"):
        problems.append("prophet_platform_response_ref must reference validate_change v2 response")
    if not str(source.get("agentplane_sandbox_run_ref", "")).startswith("agentplane:sandbox-run:"):
        problems.append("agentplane_sandbox_run_ref must reference AgentPlane sandbox run")
    if not isinstance(evidence_refs, list) or not evidence_refs:
        problems.append("evidence_refs must be a non-empty list")
    if not isinstance(receipt_refs, list) or not receipt_refs:
        problems.append("receipt_refs must be a non-empty list")
    if any(not str(ref).startswith("evidence://") for ref in evidence_refs):
        problems.append("all evidence refs must use evidence://")
    if any(not str(ref).startswith("receipt://") for ref in receipt_refs):
        problems.append("all receipt refs must use receipt://")
    if not isinstance(warning_codes, list):
        problems.append("warning_codes must be a list")
    if not isinstance(failure_codes, list):
        problems.append("failure_codes must be a list when present")

    if consequence.get("autonomy_ceiling") not in AUTONOMY:
        problems.append("autonomy_ceiling is invalid")
    if consequence.get("model_lane_ceiling") not in LANES:
        problems.append("model_lane_ceiling is invalid")
    if consequence.get("high_end_allowed") is not False:
        problems.append("high_end_allowed must remain false for this tranche")
    if consequence.get("pro_allowed") is not False:
        problems.append("pro_allowed must remain false for this tranche")
    if consequence.get("deterministic_verification_required") is not True:
        problems.append("deterministic verification must be required")
    if not isinstance(consequence.get("fallback_posture"), str) or not consequence.get("fallback_posture"):
        problems.append("fallback_posture must be present")
    if not isinstance(must_preserve, list):
        problems.append("must_preserve_warnings must be a list")
    if not set(must_preserve).issubset(set(warning_codes)):
        problems.append("must_preserve_warnings must be subset of warning_codes")

    if state == "environment_observed":
        if "observed" not in str(source.get("prophet_platform_response_ref", "")):
            problems.append("environment_observed must reference observed response")
        if "observed" not in str(source.get("agentplane_sandbox_run_ref", "")):
            problems.append("environment_observed must reference observed sandbox run")
        if consequence.get("autonomy_ceiling") != "advisory":
            problems.append("observed state must cap autonomy at advisory")
        if consequence.get("model_lane_ceiling") != "standard":
            problems.append("observed state must cap model lane at standard")
        if failure_codes:
            problems.append("observed state must not carry failure codes")
    if state == "environment_failed":
        if "failed" not in str(source.get("prophet_platform_response_ref", "")):
            problems.append("environment_failed must reference failed response")
        if "failed" not in str(source.get("agentplane_sandbox_run_ref", "")):
            problems.append("environment_failed must reference failed sandbox run")
        if consequence.get("autonomy_ceiling") != "report_only":
            problems.append("failed state must cap autonomy at report_only")
        if consequence.get("model_lane_ceiling") != "cheap":
            problems.append("failed state must cap model lane at cheap")
        if "synthetic_validation_failed" not in failure_codes:
            problems.append("failed state must preserve synthetic_validation_failed")
        if "environment_validation_failed" not in warning_codes:
            problems.append("failed state must preserve environment_validation_failed")

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
        "validator": "model-router.environment-state-routing.validator.v1",
        "passed": not failed,
        "results": results,
        "non_claims": [
            "Validator does not define environment validity.",
            "Validator does not issue or verify receipts.",
            "Validator does not grant agent autonomy."
        ]
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    print(("PASS" if not failed else "FAIL") + ": environment state routing fixtures")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
