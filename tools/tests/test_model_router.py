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


def test_route_selects_local_candidate_for_local_first_policy() -> None:
    request = model_router.load_json(ROOT / "examples" / "route-request.example.json")
    policy = model_router.load_json(ROOT / "examples" / "route-policy.example.json")
    decision = model_router.route(request, policy)

    assert decision["kind"] == "ModelRouteDecision"
    assert decision["spec"]["decisionStatus"] == "selected"
    assert decision["spec"]["selectedCandidateRef"] == "model://local/small-language@0.1.0"
    assert "privacy-local-first" in decision["spec"]["reasonCodes"]
    assert "model://hosted/frontier-language@0.1.0" in decision["spec"]["fallbackRefs"]


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
