# Price-aware routing CI trigger

This test-only change exists to trigger the newly added `model-router-ci` workflow after the workflow file landed on `main`.

Validation surface expected from CI:

```bash
python3 tools/validate_local_personal_route_bindings.py
python3 tools/validate_agent_execution_model_routing_policies.py
python3 tools/validate_agent_execution_budget_resource_optimizers.py
python3 tools/validate_model_price_catalogs.py
pytest -q tests/test_agent_execution_route_decision.py
```

No runtime semantics are changed by this file.
