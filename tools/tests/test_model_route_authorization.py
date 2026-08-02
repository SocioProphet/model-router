import copy
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from validate_model_route_authorization import (
    check,
    collect_routes,
    is_route_authorized,
)

ROOT = Path(__file__).resolve().parents[2]
ROUTING_MIRROR = ROOT / "contracts/prophet-mesh/prophet-mesh-model-routing.v0.1.json"
AUTHORIZATION = ROOT / "contracts/prophet-mesh/model-route-authorization.v0.1.json"


def _routing() -> dict:
    return json.loads(ROUTING_MIRROR.read_text(encoding="utf-8"))


def _authorization() -> dict:
    return json.loads(AUTHORIZATION.read_text(encoding="utf-8"))


def test_every_routed_model_has_a_governance_record():
    # POSITIVE: the canonical config passes -- every available route is registered.
    routes = collect_routes(_routing())
    assert routes, "expected routed models"
    assert check(routes, _authorization()) == []


def test_unledgered_routed_model_fails_closed():
    # NEGATIVE (teeth): a routed model with no authorization record is DENIED.
    routes = collect_routes(_routing())
    routes.add("phantom.unledgered-model")
    errors = check(routes, _authorization())
    assert any("phantom.unledgered-model" in e and "UNAUTHORIZED" in e for e in errors)


def test_proposed_record_is_not_runtime_authorized():
    # A scaffolded 'proposed' entry is available but NOT authorization.
    authz = _authorization()
    route = authz["route_authorizations"][0]["route"]
    assert authz["route_authorizations"][0]["status"] == "proposed"
    assert is_route_authorized(route, authz) is False


def test_authorized_requires_promotion_evidence():
    # Cannot fake-approve: 'authorized' without evidence fails closed.
    authz = _authorization()
    authz = copy.deepcopy(authz)
    rec = authz["route_authorizations"][0]
    rec["status"] = "authorized"
    rec["authorized"] = True
    rec["promotion_evidence_present"] = False
    errors = check(collect_routes(_routing()), authz)
    assert any("requires promotion_evidence_present" in e for e in errors)


def test_evidence_backed_authorization_is_runtime_authorized():
    # A genuinely evidence-backed 'authorized' record routes at runtime.
    authz = copy.deepcopy(_authorization())
    rec = authz["route_authorizations"][0]
    route = rec["route"]
    rec["status"] = "authorized"
    rec["authorized"] = True
    rec["promotion_evidence_present"] = True
    assert check(collect_routes(_routing()), authz) == []
    assert is_route_authorized(route, authz) is True


def test_unknown_route_denied_at_runtime():
    assert is_route_authorized("does.not-exist", _authorization()) is False
