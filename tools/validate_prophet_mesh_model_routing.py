#!/usr/bin/env python3
"""Validate the Prophet Mesh model-routing mirror fixture."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "contracts/prophet-mesh/prophet-mesh-model-routing.v0.1.json"

REQUIRED_TOP_LEVEL = {
    "schema_version",
    "kind",
    "source_repo",
    "source_contracts",
    "release_channel",
    "routing_posture",
    "default_conductor",
    "required_controls",
    "model_families",
    "task_routes",
    "private_preview_invariants",
    "non_claims",
}
REQUIRED_CONTROLS = {
    "identity",
    "policy",
    "evidence",
    "attestation",
    "revocation",
    "audit",
    "tenant_isolation",
}
REQUIRED_FAMILIES = {
    "hosted_frontier",
    "hosted_balanced",
    "hosted_fast",
    "open_private",
    "code_specialist",
    "reasoning_specialist",
    "image_specialist",
    "media_specialist",
    "document_specialist",
}
REQUIRED_TASKS = {
    "chat",
    "text_message_reply",
    "email_reply",
    "office_document_creation",
    "office_document_editing",
    "research",
    "coding",
    "code_review",
    "image_generation",
    "image_editing",
    "video_generation",
    "analytics",
    "operations_plan",
    "legal_compliance_draft",
    "scientific_reasoning",
}


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("fixture must be a JSON object")
    return data


def _non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _non_empty_list(value: Any) -> bool:
    return isinstance(value, list) and bool(value)


def validate(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    missing = REQUIRED_TOP_LEVEL - set(data)
    if missing:
        errors.append("missing top-level fields: " + ", ".join(sorted(missing)))

    if data.get("kind") != "prophet_mesh_model_routing_mirror":
        errors.append("kind must be prophet_mesh_model_routing_mirror")
    if data.get("source_repo") != "SocioProphet/prophet-mesh":
        errors.append("source_repo must be SocioProphet/prophet-mesh")
    if data.get("release_channel") != "private_preview":
        errors.append("release_channel must be private_preview")
    if data.get("default_conductor") != "michael-agent":
        errors.append("default_conductor must be michael-agent")

    if not _non_empty_list(data.get("source_contracts")):
        errors.append("source_contracts must be a non-empty list")
    if not _non_empty_list(data.get("private_preview_invariants")):
        errors.append("private_preview_invariants must be a non-empty list")
    if not _non_empty_list(data.get("non_claims")):
        errors.append("non_claims must be a non-empty list")
    else:
        non_claims_text = " ".join(str(item).lower() for item in data["non_claims"])
        for phrase in [
            "does not call hosted providers",
            "does not store provider credentials",
            "does not execute external actions",
            "does not certify model safety",
            "does not certify production autonomy",
        ]:
            if not all(word in non_claims_text for word in phrase.split()):
                errors.append(f"non_claims missing boundary: {phrase}")

    controls = {str(item) for item in data.get("required_controls", [])}
    missing_controls = REQUIRED_CONTROLS - controls
    if missing_controls:
        errors.append("required_controls missing: " + ", ".join(sorted(missing_controls)))

    families = data.get("model_families", [])
    if not _non_empty_list(families):
        errors.append("model_families must be a non-empty list")
    else:
        family_ids: set[str] = set()
        for index, family in enumerate(families):
            if not isinstance(family, dict):
                errors.append(f"model_families[{index}] must be an object")
                continue
            family_id = family.get("id")
            if not _non_empty_string(family_id):
                errors.append(f"model_families[{index}].id must be a non-empty string")
                continue
            if family_id in family_ids:
                errors.append(f"duplicate model family: {family_id}")
            family_ids.add(str(family_id))
            if not _non_empty_string(family.get("role")):
                errors.append(f"model_families[{index}].role must be a non-empty string")
            if not _non_empty_list(family.get("preferred_routes")):
                errors.append(f"model_families[{index}].preferred_routes must be a non-empty list")
            if not isinstance(family.get("requires_hosted_approval"), bool):
                errors.append(f"model_families[{index}].requires_hosted_approval must be boolean")
        missing_families = REQUIRED_FAMILIES - family_ids
        if missing_families:
            errors.append("missing required model families: " + ", ".join(sorted(missing_families)))

    tasks = data.get("task_routes", [])
    if not _non_empty_list(tasks):
        errors.append("task_routes must be a non-empty list")
    else:
        task_ids: set[str] = set()
        known_families = {str(family.get("id")) for family in families if isinstance(family, dict)}
        for index, route in enumerate(tasks):
            if not isinstance(route, dict):
                errors.append(f"task_routes[{index}] must be an object")
                continue
            task = route.get("task")
            if not _non_empty_string(task):
                errors.append(f"task_routes[{index}].task must be a non-empty string")
                continue
            if task in task_ids:
                errors.append(f"duplicate task route: {task}")
            task_ids.add(str(task))
            for key in ("domain", "primary_family", "private_family"):
                if not _non_empty_string(route.get(key)):
                    errors.append(f"task_routes[{index}].{key} must be a non-empty string")
            if route.get("primary_family") not in known_families:
                errors.append(f"task_routes[{index}].primary_family must reference a known family")
            if route.get("private_family") not in known_families:
                errors.append(f"task_routes[{index}].private_family must reference a known family")
            if route.get("requires_evidence") is not True:
                errors.append(f"task_routes[{index}].requires_evidence must be true")
            if route.get("external_action_allowed") is not False:
                errors.append(f"task_routes[{index}].external_action_allowed must be false")
            if task in {"email_reply", "operations_plan"} and route.get("policy_decision") != "requires_approval":
                errors.append(f"task_routes[{index}].policy_decision must be requires_approval for {task}")
        missing_tasks = REQUIRED_TASKS - task_ids
        if missing_tasks:
            errors.append("missing required task routes: " + ", ".join(sorted(missing_tasks)))

    return errors


def main() -> int:
    try:
        data = _load_json(FIXTURE)
    except Exception as exc:  # pragma: no cover - defensive CLI path
        print(f"ERR: failed to load {FIXTURE}: {exc}", file=sys.stderr)
        return 2

    errors = validate(data)
    report = {
        "validator": "model-router.prophet-mesh-model-routing.validator.v1",
        "passed": not errors,
        "problems": errors,
        "fixture": str(FIXTURE.relative_to(ROOT)),
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    print(("PASS" if not errors else "FAIL") + ": Prophet Mesh model routing mirror")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
