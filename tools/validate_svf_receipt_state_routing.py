#!/usr/bin/env python3
"""Validate model-router SVF receipt-state routing fixtures.

This validator checks consumer fixture shape and policy consequences. It does
not define SVF validity, execute validations, or issue receipts.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples" / "svf-receipt-state-routing-policy.default.json"

STATUSES = {"validated", "selected_missing_observation", "not_configured", "failed", "stale"}
AUTONOMY = {"report_only", "advisory", "human_review_required", "bounded_autonomy"}
LANES = {"no_model", "local_cheap", "cheap", "standard", "high_end", "pro"}


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def result(check_id: str, passed: bool, diagnostics: list[str] | None = None) -> dict[str, Any]:
    return {"check_id": check_id, "passed": passed, "diagnostics": diagnostics or []}


def validate() -> dict[str, Any]:
    data = load(FIXTURE)
    results: list[dict[str, Any]] = []

    results.append(result("schema-version", data.get("schema_version") == "1.0"))
    results.append(result("policy-id", str(data.get("policy_id", "")).startswith("svf:receipt-state-routing-policy:"), [str(data.get("policy_id"))]))
    results.append(result("owner-plane", data.get("owner", {}).get("plane") == "model-router"))
    results.append(result("owner-repo", data.get("owner", {}).get("repo") == "SocioProphet/model-router"))

    inputs = data.get("inputs", {})
    results.append(result("input-repo", "/" in str(inputs.get("repo", "")), [str(inputs.get("repo"))]))
    results.append(result("input-ref", isinstance(inputs.get("ref"), str) and len(inputs["ref"]) > 0))
    plans = inputs.get("selected_plans", [])
    results.append(result("selected-plans", isinstance(plans, list) and len(plans) > 0))
    for idx, plan in enumerate(plans if isinstance(plans, list) else []):
        prefix = f"plan[{idx}]"
        results.append(result(f"{prefix}-id", str(plan.get("plan_id", "")).startswith("svf:plan:"), [str(plan.get("plan_id"))]))
        results.append(result(f"{prefix}-mode", plan.get("mode") in {"advisory", "blocking"}, [str(plan.get("mode"))]))
        results.append(result(f"{prefix}-required-observations", isinstance(plan.get("required_observations"), list)))

    status = inputs.get("validation_status")
    results.append(result("validation-status", status in STATUSES, [str(status)]))
    warnings = set(inputs.get("warnings", [])) if isinstance(inputs.get("warnings"), list) else set()
    receipts = inputs.get("receipt_refs", [])
    observed = inputs.get("observed_validation_commands", [])
    results.append(result("receipt-refs-list", isinstance(receipts, list)))
    results.append(result("observed-commands-list", isinstance(observed, list)))

    consequence = data.get("routing_consequence", {})
    results.append(result("autonomy-ceiling", consequence.get("autonomy_ceiling") in AUTONOMY, [str(consequence.get("autonomy_ceiling"))]))
    results.append(result("model-lane-ceiling", consequence.get("model_lane_ceiling") in LANES, [str(consequence.get("model_lane_ceiling"))]))
    results.append(result("high-end-boolean", isinstance(consequence.get("high_end_allowed"), bool)))
    results.append(result("pro-boolean", isinstance(consequence.get("pro_allowed"), bool)))
    results.append(result("deterministic-verification-boolean", isinstance(consequence.get("deterministic_verification_required"), bool)))
    results.append(result("fallback-posture-present", isinstance(consequence.get("fallback_posture"), str) and len(consequence["fallback_posture"]) > 0))

    must_preserve = set(consequence.get("must_preserve_warnings", [])) if isinstance(consequence.get("must_preserve_warnings"), list) else set()
    results.append(result("preserve-warnings-subset", must_preserve.issubset(warnings), [f"must={sorted(must_preserve)}", f"warnings={sorted(warnings)}"]))

    if status == "selected_missing_observation":
        results.append(result("missing-observation-warning-present", "validation_observation_missing" in warnings, sorted(warnings)))
        results.append(result("missing-observation-no-receipts", receipts == [], [str(receipts)]))
        results.append(result("missing-observation-no-observed-commands", observed == [], [str(observed)]))
        results.append(result("missing-observation-report-only", consequence.get("autonomy_ceiling") == "report_only", [str(consequence.get("autonomy_ceiling"))]))
        results.append(result("missing-observation-high-end-denied", consequence.get("high_end_allowed") is False))
        results.append(result("missing-observation-pro-denied", consequence.get("pro_allowed") is False))
        results.append(result("missing-observation-deterministic-required", consequence.get("deterministic_verification_required") is True))

    results.append(result("non-claims-present", isinstance(data.get("non_claims"), list) and len(data.get("non_claims", [])) >= 3))

    passed = all(item["passed"] for item in results)
    return {
        "validator": "model-router.svf-receipt-state-routing.validator.v1",
        "passed": passed,
        "result_count": len(results),
        "results": results,
    }


def main() -> int:
    validation = validate()
    print(json.dumps(validation, indent=2, sort_keys=True))
    if not validation["passed"]:
        print("FAIL: SVF receipt-state routing", file=sys.stderr)
        return 1
    print("PASS: SVF receipt-state routing")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
