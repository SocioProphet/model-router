.PHONY: validate test emit-demo-decision release-dry-run

validate:
	python3 tools/validate_route_examples.py

test:
	python3 -m pytest -q tools/tests

emit-demo-decision:
	python3 tools/model_router.py emit-demo-decision --output dist/route-decision.demo.json
	@cat dist/route-decision.demo.json

release-dry-run: validate test
	python3 tools/release_dry_run.py
