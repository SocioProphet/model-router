#!/usr/bin/env python3
"""Validate Professional Intelligence routing-decision examples."""

from __future__ import annotations

from pathlib import Path
import json

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "schemas" / "professional-intelligence-routing-decision.schema.json"
EXAMPLE_DIR = ROOT / "examples" / "professional-intelligence"


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def main() -> int:
    schema = load_json(SCHEMA)
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)

    examples = sorted(EXAMPLE_DIR.glob("routing-decision.*.example.json"))
    if not examples:
        print(f"No routing decision examples found under {EXAMPLE_DIR.relative_to(ROOT)}")
        return 1

    failures: list[str] = []
    for example_path in examples:
        example = load_json(example_path)
        errors = sorted(validator.iter_errors(example), key=lambda error: list(error.path))
        for error in errors:
            location = ".".join(str(part) for part in error.path) or "<root>"
            failures.append(f"{example_path.relative_to(ROOT)} {location}: {error.message}")

        candidates = {candidate["routeId"]: candidate for candidate in example["candidateRoutes"]}
        selected = example["selectedRoute"]
        fallback = example["fallbackRoute"]
        if selected not in candidates:
            failures.append(f"{example_path.relative_to(ROOT)}: selectedRoute is not a candidate route")
        elif not candidates[selected]["allowed"]:
            failures.append(f"{example_path.relative_to(ROOT)}: selectedRoute must be allowed")
        if fallback not in candidates:
            failures.append(f"{example_path.relative_to(ROOT)}: fallbackRoute is not a candidate route")
        elif not candidates[fallback]["allowed"]:
            failures.append(f"{example_path.relative_to(ROOT)}: fallbackRoute must be allowed")

        constraints = example["constraints"]
        selected_candidate = candidates.get(selected)
        if selected_candidate:
            if selected_candidate["estimatedLatencyMs"] > constraints["latencyBudgetMs"]:
                failures.append(f"{example_path.relative_to(ROOT)}: selectedRoute exceeds latency budget")
            if selected_candidate["estimatedCostUsd"] > constraints["costCeilingUsd"]:
                failures.append(f"{example_path.relative_to(ROOT)}: selectedRoute exceeds cost ceiling")
            if selected_candidate["qualityScore"] < constraints["minQualityScore"]:
                failures.append(f"{example_path.relative_to(ROOT)}: selectedRoute misses quality threshold")
        if constraints["evidenceRequired"] and not example.get("evidenceRefs"):
            failures.append(f"{example_path.relative_to(ROOT)}: evidenceRefs required by constraints")
        if not example.get("policyDecisionRefs"):
            failures.append(f"{example_path.relative_to(ROOT)}: policyDecisionRefs required")

    if failures:
        print("Professional Intelligence routing validation failed:")
        for failure in failures:
            print(f" - {failure}")
        return 1

    print(f"Professional Intelligence routing examples validate: {len(examples)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
