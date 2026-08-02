from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "tools" / "model_router.py"
spec = importlib.util.spec_from_file_location("model_router", MODULE_PATH)
assert spec and spec.loader
model_router = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model_router)


AUTH_LOCAL = "meta_llama.llama-4-scout"
AUTH_HOSTED = "anthropic.claude-opus-4.8"


def _authorize(*routes: str) -> dict:
    """Build a runtime authorization mirror that evidence-backs the given routes."""
    return {
        "realizes_invariant": "model_availability_is_not_authorization",
        "posture": "fail_closed",
        "route_authorizations": [
            {
                "route": route,
                "status": "authorized",
                "authorized": True,
                "promotion_evidence_present": True,
                "ledger_entry": f"model://prophet-mesh/{route}@test-authorized",
            }
            for route in routes
        ],
    }


def test_route_selects_local_candidate_for_local_first_policy() -> None:
    request = model_router.load_json(ROOT / "examples" / "route-request.example.json")
    policy = model_router.load_json(ROOT / "examples" / "route-policy.example.json")
    # Authorize both governance routes so this test isolates policy/scoring.
    decision = model_router.route(request, policy, authorization=_authorize(AUTH_LOCAL, AUTH_HOSTED))

    assert decision["kind"] == "ModelRouteDecision"
    assert decision["spec"]["decisionStatus"] == "selected"
    assert decision["spec"]["selectedCandidateRef"] == "model://local/small-language@0.1.0"
    assert decision["spec"]["selectedGovernanceRoute"] == AUTH_LOCAL
    assert "authorized" in decision["spec"]["reasonCodes"]
    assert "privacy-local-first" in decision["spec"]["reasonCodes"]
    # Both authorized -> hosted is an eligible fallback, not blocked.
    assert "model://hosted/frontier-language@0.1.0" in decision["spec"]["fallbackRefs"]


def test_runtime_denies_unledgered_model_even_when_it_would_win() -> None:
    # TEETH (deny): the hosted candidate scores highest AND is policy-eligible,
    # but its governance route is only 'proposed' (no promotion evidence). It
    # MUST be denied at runtime and MUST NOT be selected or offered as fallback.
    request = model_router.load_json(ROOT / "examples" / "route-request.example.json")
    policy = model_router.load_json(ROOT / "examples" / "route-policy.example.json")
    # Force a policy where the hosted candidate would otherwise be selected.
    policy["spec"]["preferLocal"] = False
    policy["spec"]["privacyMode"] = "standard"
    # Authorize ONLY the local route; hosted (anthropic.claude-opus-4.8) unledgered.
    decision = model_router.route(request, policy, authorization=_authorize(AUTH_LOCAL))

    assert decision["spec"]["decisionStatus"] == "selected"
    assert decision["spec"]["selectedCandidateRef"] == "model://local/small-language@0.1.0"
    assert "model://hosted/frontier-language@0.1.0" in decision["spec"]["blockedCandidateRefs"]
    assert "model://hosted/frontier-language@0.1.0" not in decision["spec"]["fallbackRefs"]


def test_runtime_authorizes_evidence_backed_model() -> None:
    # TEETH (allow): the same model routes when its governance route is
    # authorized with promotion evidence.
    request = model_router.load_json(ROOT / "examples" / "route-request.example.json")
    policy = model_router.load_json(ROOT / "examples" / "route-policy.example.json")
    decision = model_router.route(request, policy, authorization=_authorize(AUTH_LOCAL, AUTH_HOSTED))
    assert decision["spec"]["decisionStatus"] == "selected"
    assert decision["spec"]["blockedCandidateRefs"] == []


def test_runtime_blocks_all_when_no_route_authorized() -> None:
    # Empty authorization mirror -> every available candidate is denied.
    request = model_router.load_json(ROOT / "examples" / "route-request.example.json")
    policy = model_router.load_json(ROOT / "examples" / "route-policy.example.json")
    decision = model_router.route(request, policy, authorization=_authorize())
    assert decision["spec"]["decisionStatus"] == "blocked"
    assert decision["spec"]["selectedCandidateRef"] == ""
    assert "no-authorized-candidates" in decision["spec"]["reasonCodes"]
    assert set(decision["spec"]["blockedCandidateRefs"]) == set(decision["spec"]["candidateRefs"])


def test_runtime_denies_candidate_without_governance_route() -> None:
    # A candidate that does not declare which governed model it is cannot be
    # authorized -- fail closed, do not default-allow.
    request = model_router.load_json(ROOT / "examples" / "route-request.example.json")
    policy = model_router.load_json(ROOT / "examples" / "route-policy.example.json")
    for candidate in request["spec"]["candidates"]:
        candidate.pop("governanceRoute", None)
    decision = model_router.route(request, policy, authorization=_authorize(AUTH_LOCAL, AUTH_HOSTED))
    assert decision["spec"]["decisionStatus"] == "blocked"
    assert set(decision["spec"]["blockedCandidateRefs"]) == set(decision["spec"]["candidateRefs"])


def test_runtime_denies_against_production_proposed_contract() -> None:
    # Teeth vs the REAL governance state: the production authorization contract
    # currently lists every route as 'proposed'. With no override, route() reads
    # that contract and denies every available demo candidate. This is the exact
    # gap that was CI-only before: at runtime the model is now blocked.
    request = model_router.load_json(ROOT / "examples" / "route-request.example.json")
    request["spec"].pop("authorizationRef", None)  # fall through to production contract
    policy = model_router.load_json(ROOT / "examples" / "route-policy.example.json")
    decision = model_router.route(request, policy)  # default = production contract
    assert decision["spec"]["decisionStatus"] == "blocked"
    assert decision["spec"]["selectedCandidateRef"] == ""


def test_route_blocks_when_threshold_excludes_all_candidates() -> None:
    request = model_router.load_json(ROOT / "examples" / "route-request.example.json")
    policy = model_router.load_json(ROOT / "examples" / "route-policy.example.json")
    policy["spec"]["minimumEvalConfidence"] = 0.99
    decision = model_router.route(request, policy)

    assert decision["spec"]["decisionStatus"] == "blocked"
    assert decision["spec"]["selectedCandidateRef"] == ""
    assert decision["spec"]["reasonCodes"] == ["no-eligible-candidates"]


def test_cli_emits_demo_decision(tmp_path: Path) -> None:
    out = tmp_path / "decision.json"
    result = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "model_router.py"), "emit-demo-decision", "--output", str(out)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["kind"] == "ModelRouteDecision"
    assert payload["spec"]["policyRef"] == "policy://model-router/local-first-v1"
