.PHONY: validate test emit-demo-decision release-dry-run validate-superconscious-reasoning-route validate-svf-receipt-state-routing

validate: validate-superconscious-reasoning-route validate-svf-receipt-state-routing
	python3 tools/validate_route_examples.py

validate-superconscious-reasoning-route:
	python3 tools/validate_superconscious_reasoning_route.py

validate-svf-receipt-state-routing:
	python3 tools/validate_svf_receipt_state_routing.py

test:
	python3 -m pytest -q tools/tests

emit-demo-decision:
	python3 tools/model_router.py emit-demo-decision --output dist/route-decision.demo.json
	@cat dist/route-decision.demo.json

release-dry-run: validate test
	python3 tools/release_dry_run.py
