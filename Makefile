.PHONY: validate test emit-demo-decision release-dry-run validate-superconscious-reasoning-route validate-svf-receipt-state-routing validate-trust-chain-model-route-decision validate-prophet-mesh-model-routing

validate: validate-superconscious-reasoning-route validate-svf-receipt-state-routing validate-trust-chain-model-route-decision validate-prophet-mesh-model-routing
	python3 tools/validate_route_examples.py

validate-superconscious-reasoning-route:
	python3 tools/validate_superconscious_reasoning_route.py

validate-svf-receipt-state-routing:
	python3 tools/validate_svf_receipt_state_routing.py

validate-trust-chain-model-route-decision:
	python3 -m json.tool schemas/trust-chain-model-route-decision.v0.1.schema.json >/dev/null
	python3 -m json.tool examples/trust-chain-model-route-decision.allow.json >/dev/null
	python3 -m json.tool examples/trust-chain-model-route-decision.fallback.json >/dev/null
	python3 -m json.tool examples/trust-chain-model-route-decision.deny.json >/dev/null
	python3 tools/validate_trust_chain_model_route_decision.py

validate-prophet-mesh-model-routing:
	python3 -m json.tool contracts/prophet-mesh/prophet-mesh-model-routing.v0.1.json >/dev/null
	python3 tools/validate_prophet_mesh_model_routing.py

test:
	python3 -m pytest -q tools/tests

emit-demo-decision:
	python3 tools/model_router.py emit-demo-decision --output dist/route-decision.demo.json
	@cat dist/route-decision.demo.json

release-dry-run: validate test
	python3 tools/release_dry_run.py
