from __future__ import annotations

import json
from pathlib import Path

from tools.validate_trust_chain_model_route_decision import main as validate_trust_chain_model_route_decision


ROOT = Path(__file__).resolve().parents[2]
ALLOW_FIXTURE = ROOT / "examples" / "trust-chain-model-route-decision.allow.json"
FALLBACK_FIXTURE = ROOT / "examples" / "trust-chain-model-route-decision.fallback.json"
DENY_FIXTURE = ROOT / "examples" / "trust-chain-model-route-decision.deny.json"


def test_trust_chain_model_route_decision_validator() -> None:
    assert validate_trust_chain_model_route_decision() == 0


def test_allow_route_uses_admitted_local_runtime_without_prompt_egress() -> None:
    fixture = json.loads(ALLOW_FIXTURE.read_text(encoding="utf-8"))
    assert fixture["decision"] == "allow"
    assert fixture["selected_route"] == "model-route://model-router/local-small-language-production"
    assert fixture["effects"]["route_allowed"] is True
    assert fixture["effects"]["provider_call_allowed"] is False
    assert fixture["effects"]["prompt_egress_allowed"] is False


def test_fallback_route_preserves_local_first_when_provider_evidence_missing() -> None:
    fixture = json.loads(FALLBACK_FIXTURE.read_text(encoding="utf-8"))
    assert fixture["decision"] == "fallback"
    assert fixture["selected_route"] == "model-route://model-router/local-small-language-production"
    assert fixture["effects"]["fallback_required"] is True
    assert fixture["effects"]["prompt_egress_allowed"] is False
    preferred = fixture["candidate_routes"][0]
    assert preferred["trust_chain_refs"]["runtime_or_provider_admission_ref"] is None


def test_denied_route_selects_no_candidate_and_requires_remediation() -> None:
    fixture = json.loads(DENY_FIXTURE.read_text(encoding="utf-8"))
    assert fixture["decision"] == "deny"
    assert fixture["selected_route"] is None
    assert fixture["effects"]["route_allowed"] is False
    assert fixture["effects"]["human_review_required"] is True
    assert fixture["remediation"]
    assert all(item["required_before_route"] is True for item in fixture["remediation"])
