import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "agent_execution_route_decision.py"
EXAMPLES = ROOT / "examples"


def run_decision(*args: str) -> dict:
    command = [
        sys.executable,
        str(SCRIPT),
        "--compact",
        *args,
    ]
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    return json.loads(result.stdout)


def test_formatting_high_end_request_downgrades_to_cheap():
    decision = run_decision(
        "--resources",
        str(EXAMPLES / "resources.healthy-local.json"),
        "--task-class",
        "formatting-rewrite",
        "--stage",
        "planning",
        "--risk-class",
        "low",
        "--requested-lane",
        "high-end",
    )

    assert decision["selected"]["status"] == "downgraded"
    assert decision["selected"]["lane"] == "cheap"


def test_architecture_decision_allows_high_end_with_reason():
    decision = run_decision(
        "--resources",
        str(EXAMPLES / "resources.healthy-local.json"),
        "--task-class",
        "architecture-decision",
        "--stage",
        "planning",
        "--risk-class",
        "high",
        "--requested-lane",
        "high-end",
        "--escalation-reason",
        "architecture-decision",
    )

    assert decision["selected"]["lane"] == "high-end"
    assert decision["selected"]["status"] == "selected"


def test_verification_prefers_no_model():
    decision = run_decision(
        "--resources",
        str(EXAMPLES / "resources.healthy-local.json"),
        "--task-class",
        "routine-code",
        "--stage",
        "verification",
        "--risk-class",
        "medium",
    )

    assert decision["selected"]["lane"] == "standard"
    assert decision["quality"]["requiresVerification"] is True


def test_pro_without_reason_is_deferred():
    decision = run_decision(
        "--resources",
        str(EXAMPLES / "resources.healthy-local.json"),
        "--task-class",
        "high-stakes-synthesis",
        "--stage",
        "review",
        "--risk-class",
        "critical",
        "--requested-lane",
        "pro",
    )

    requested = decision["requestedEvaluation"]
    assert requested["feasible"] is False
    assert "premium-lane-requires-escalation-reason" in requested["reasons"]


def test_budget_pressure_downgrades_high_end_request():
    decision = run_decision(
        "--resources",
        str(EXAMPLES / "resources.healthy-local.json"),
        "--task-class",
        "routine-code",
        "--stage",
        "planning",
        "--risk-class",
        "medium",
        "--requested-lane",
        "high-end",
        "--budget-remaining",
        "0.10",
    )

    assert decision["selected"]["lane"] in {"local-cheap", "cheap", "standard"}
    assert decision["selected"]["status"] == "downgraded"


def test_thermal_critical_skips_local_lane():
    decision = run_decision(
        "--resources",
        str(EXAMPLES / "resources.thermal-critical.json"),
        "--task-class",
        "log-triage",
        "--stage",
        "classification",
        "--risk-class",
        "low",
    )

    local_candidate = next(item for item in decision["candidateSet"] if item["lane"] == "local-cheap")
    assert local_candidate["feasible"] is False
    assert "thermal-critical" in local_candidate["reasons"]


def test_unknown_quota_blocks_premium_lane():
    decision = run_decision(
        "--resources",
        str(EXAMPLES / "resources.unknown-premium-quota.json"),
        "--task-class",
        "security-review",
        "--stage",
        "review",
        "--risk-class",
        "high",
        "--requested-lane",
        "high-end",
        "--escalation-reason",
        "security-review",
    )

    requested = decision["requestedEvaluation"]
    assert requested["feasible"] is False
    assert "provider-quota-unknown" in requested["reasons"]
