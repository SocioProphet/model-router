#!/usr/bin/env python3
"""Fail-closed model-route authorization gate.

Realizes the Prophet Mesh invariant ``model_availability_is_not_authorization``:
a model may appear in the routing mirror (it is *available*) yet still be
*unauthorized* to be routed to. Authorization exists only when the Model
Governance Ledger holds approved promotion evidence for that model.

This gate DENIES (fails closed) any route present in the routing mirror that
does not carry a governance authorization record. It does not, and cannot,
grant authorization -- that happens only in SocioProphet/model-governance-ledger
by a release authority. See SocioProphet/model-governance-ledger#29 and the
Model Plane work in SocioProphet/prophet-platform#240.

Two levels of enforcement:

* ``check(routes, authorization)`` -- the CONFORMANCE gate (CI). Every routed
  model must carry a governance record whose status is known
  (authorized/proposed/denied). A routed model with NO record fails closed.
  A record claiming ``authorized`` without promotion evidence fails closed.
* ``is_route_authorized(route, authorization)`` -- the RUNTIME decision. Returns
  True only for a model with an ``authorized`` record backed by promotion
  evidence. proposed / denied / unknown all deny.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ROUTING_MIRROR = ROOT / "contracts/prophet-mesh/prophet-mesh-model-routing.v0.1.json"
AUTHORIZATION = ROOT / "contracts/prophet-mesh/model-route-authorization.v0.1.json"

VALID_STATES = {"authorized", "proposed", "denied"}
INVARIANT = "model_availability_is_not_authorization"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def collect_routes(routing: dict[str, Any]) -> set[str]:
    """Every model route that is reachable through the task routes.

    A model is "available" if some task route selects a family that lists it as
    a preferred route. That is exactly the surface that must be authorized.
    """
    families = {f.get("id"): f for f in routing.get("model_families", []) if isinstance(f, dict)}
    used: set[str] = set()
    for route in routing.get("task_routes", []):
        if not isinstance(route, dict):
            continue
        for key in ("primary_family", "private_family"):
            fam = families.get(route.get(key))
            if fam:
                for candidate in fam.get("preferred_routes", []):
                    if isinstance(candidate, str) and candidate.strip():
                        used.add(candidate)
    return used


def index_authorization(authorization: dict[str, Any]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for record in authorization.get("route_authorizations", []):
        if isinstance(record, dict) and isinstance(record.get("route"), str):
            index[record["route"]] = record
    return index


def check(routes: set[str], authorization: dict[str, Any]) -> list[str]:
    """Fail-closed conformance check. Returns a list of problems (empty == pass)."""
    errors: list[str] = []

    if authorization.get("realizes_invariant") != INVARIANT:
        errors.append(f"authorization mirror must declare realizes_invariant={INVARIANT}")
    if authorization.get("posture") != "fail_closed":
        errors.append("authorization mirror posture must be fail_closed")

    index = index_authorization(authorization)

    # Fail closed on the unknown: an available route with no governance record
    # is DENIED, not silently allowed. This is the teeth of the invariant.
    for route in sorted(routes):
        record = index.get(route)
        if record is None:
            errors.append(
                f"UNAUTHORIZED (fail-closed): routed model '{route}' has no Model Governance "
                f"Ledger authorization record ({INVARIANT})"
            )
            continue
        status = record.get("status")
        if status not in VALID_STATES:
            errors.append(f"route '{route}': status must be one of {sorted(VALID_STATES)}, got {status!r}")
            continue
        authorized_flag = record.get("authorized")
        evidence = record.get("promotion_evidence_present")
        ledger_entry = record.get("ledger_entry")
        if not isinstance(ledger_entry, str) or not ledger_entry.startswith("model://"):
            errors.append(f"route '{route}': ledger_entry must be a model:// URI")
        # authorized flag must be consistent with status -- no silent elevation.
        if authorized_flag is not (status == "authorized"):
            errors.append(f"route '{route}': authorized flag must be {status == 'authorized'} for status '{status}'")
        # An authorized record MUST be backed by promotion evidence. Cannot fake-approve.
        if status == "authorized" and evidence is not True:
            errors.append(
                f"route '{route}': status 'authorized' requires promotion_evidence_present=true "
                f"(availability is not authorization)"
            )
        if status != "authorized" and evidence is True:
            errors.append(f"route '{route}': non-authorized record must not claim promotion_evidence_present=true")

    # Orphan records: an authorization for a route that is not in the config keeps
    # the mirror honest and prevents pre-authorizing routes that don't exist yet.
    for route in sorted(index):
        if route not in routes:
            errors.append(f"orphan authorization record for '{route}': route not present in routing mirror")

    return errors


def is_route_authorized(route: str, authorization: dict[str, Any]) -> bool:
    """Runtime fail-closed decision. True only for an evidence-backed authorization."""
    record = index_authorization(authorization).get(route)
    if not record:
        return False
    return record.get("status") == "authorized" and record.get("promotion_evidence_present") is True


def _prove_teeth() -> list[str]:
    """Self-proof that the gate has teeth on the negative case.

    Inject a phantom available route with no authorization record and assert the
    gate denies it. Returns problems if the teeth are missing.
    """
    problems: list[str] = []
    authorization = load_json(AUTHORIZATION)
    phantom = "phantom.unledgered-model"
    neg = check({phantom}, authorization)
    if not any(phantom in e and "UNAUTHORIZED" in e for e in neg):
        problems.append("teeth check failed: an unledgered routed model was NOT denied")
    if is_route_authorized(phantom, authorization):
        problems.append("teeth check failed: unledgered route reported authorized at runtime")
    return problems


def main() -> int:
    routing = load_json(ROUTING_MIRROR)
    authorization = load_json(AUTHORIZATION)
    routes = collect_routes(routing)
    errors = check(routes, authorization)
    teeth = _prove_teeth()

    index = index_authorization(authorization)
    authorized = sorted(r for r in routes if is_route_authorized(r, authorization))
    report = {
        "gate": "model-router.model-route-authorization.gate.v1",
        "invariant": INVARIANT,
        "routed_models": len(routes),
        "with_governance_record": sum(1 for r in routes if r in index),
        "runtime_authorized": len(authorized),
        "runtime_denied": sorted(r for r in routes if not is_route_authorized(r, authorization)),
        "passed": not errors and not teeth,
        "problems": errors + teeth,
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    print(("PASS" if report["passed"] else "FAIL") + ": model-route authorization gate")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
