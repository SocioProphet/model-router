import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from validate_prophet_mesh_model_routing import validate

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "contracts/prophet-mesh/prophet-mesh-model-routing.v0.1.json"


def _load_fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_prophet_mesh_model_routing_validates():
    errors = validate(_load_fixture())
    assert errors == []


def test_prophet_mesh_model_routing_rejects_missing_family():
    data = _load_fixture()
    data["model_families"] = [family for family in data["model_families"] if family["id"] != "open_private"]
    errors = validate(data)
    assert any("missing required model families" in error for error in errors)


def test_prophet_mesh_model_routing_rejects_external_action_execution():
    data = _load_fixture()
    data["task_routes"][0]["external_action_allowed"] = True
    errors = validate(data)
    assert any("external_action_allowed must be false" in error for error in errors)


def test_prophet_mesh_model_routing_rejects_email_without_approval():
    data = _load_fixture()
    for route in data["task_routes"]:
        if route["task"] == "email_reply":
            route["policy_decision"] = "allow"
    errors = validate(data)
    assert any("requires_approval" in error and "email_reply" in error for error in errors)
