# model-router

Governed model and service routing for SocioProphet: local vs hosted, small vs large, cost, latency, quality, privacy, fallback, and eval-confidence policy.

## Professional Intelligence routing decisions

Model Router now carries the first Professional Intelligence OS routing-decision surface for Gate 3.

The routing contract and examples live at:

- `schemas/professional-intelligence-routing-decision.schema.json`
- `examples/professional-intelligence/routing-decision.review-packet.example.json`
- `examples/professional-intelligence/routing-decision.policy-sensitive-summary.example.json`

Validate locally:

```bash
python -m pip install jsonschema
python scripts/validate_professional_intelligence_routing.py
```

The workflow `.github/workflows/professional-intelligence-routing.yml` runs this validation when the routing schema, examples, validator, or workflow changes.

The seed route decisions demonstrate how Professional Intelligence workflow steps choose local, hosted, service, or fallback routes using:

- privacy class;
- latency budget;
- cost ceiling;
- quality threshold;
- evidence requirement;
- local preference;
- hosted-model policy;
- policy decision references;
- fallback route requirements.

This supports the Gate 3 demo path by connecting Agent Registry authority, Policy Fabric decisions, Memory Mesh context packs, Prophet Workspace workrooms, and downstream Model Governance Ledger evidence.
