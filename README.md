# model-router

Governed model and service routing for SocioProphet: local vs hosted, small vs large, cost, latency, quality, privacy, fallback, personalization, and eval-confidence policy.

## Role

`model-router` decides where a request should go. It does not own model lifecycle, local model carry profiles, per-user personalization consent, runtime admission, or provider credential handling.

## Prophet Trust Chain model route decisions

Model Router owns the route-selection slice of Prophet Trust Chain. The platform standard and admission contract live in `SocioProphet/prophet-platform`:

- `docs/standards/PROPHET_TRUST_CHAIN_V0.md`
- `docs/TRUST_CHAIN_ADMISSION_CONTRACT.md`
- `docs/standards/PROPHET_TRUST_CHAIN_IMPLEMENTATION_MAP.md`

This repo now carries `TrustChainModelRouteDecision`, which binds a requested model capability to candidate routes, model factsheets, eval receipts, runtime or hosted-provider admission refs, policy profile refs, Guardrail decision refs, cost class, fallback posture, and route effects.

Relevant files:

- `schemas/trust-chain-model-route-decision.v0.1.schema.json`
- `examples/trust-chain-model-route-decision.allow.json`
- `examples/trust-chain-model-route-decision.fallback.json`
- `examples/trust-chain-model-route-decision.deny.json`
- `tools/validate_trust_chain_model_route_decision.py`
- `tools/tests/test_trust_chain_model_route_decision.py`

Validation:

```bash
make validate-trust-chain-model-route-decision
python3 -m pytest -q tools/tests/test_trust_chain_model_route_decision.py
```

The allow fixture routes to an admitted local model/runtime with model factsheet, eval receipt, runtime admission, policy profile, and Guardrail evidence present. Provider call and prompt egress remain denied.

The fallback fixture rejects a preferred hosted/provider route because provider admission evidence is missing, then falls back to the admitted local route while preserving local-first routing and prompt-egress denial.

The deny fixture proves fail-closed behavior: when no candidate route has complete Trust Chain evidence, no route is selected and remediation is required before routing.

Boundary: Model Router selects routes under policy and evidence constraints. It does not call live providers, store provider credentials, treat model availability as authorization, replace Model Governance Ledger model promotion evidence, replace Lattice Forge runtime evidence, replace Policy Fabric policy profiles, replace Guardrail Fabric action admission, replace AgentPlane execution evidence, or replace Prophet Platform admission composition.

## Local + personal routing

The router now has a contract surface for routing between:

- base local model profiles from `SourceOS-Linux/sourceos-model-carry`;
- per-user personalization artifacts governed by `SocioProphet/model-governance-ledger`;
- higher-quality local fallback profiles;
- hosted fallbacks that require policy approval.

Contract and example:

```text
schemas/local-personal-route-binding.schema.json
examples/local-personal-route-binding.llama32.json
tools/validate_local_personal_route_bindings.py
```

## Agent execution routing policy

The router also owns the canonical policy for model use inside agent execution chains. The policy converts the operating rule into a machine-readable contract:

```text
Use the cheapest lane that can safely complete the next irreversible decision.
```

The contract defines no-model, local-cheap, cheap, standard, high-end, and pro lanes; task classes; chain stages; escalation reasons; context limits; tool-use gates; and evidence requirements.

Contract and example:

```text
schemas/agent-execution-model-routing-policy.schema.json
examples/agent-execution-model-routing-policy.default.json
tools/validate_agent_execution_model_routing_policies.py
docs/agent-execution-model-routing-policy.md
```

## Budget and resource optimizer

Routing is also constrained by budget and live resource availability. The optimizer chooses the cheapest acceptable lane subject to policy, privacy, safety, quality floor, budget ceilings, local resource health, provider quota, provider health, latency, and deterministic verification availability.

Contract and example:

```text
schemas/agent-execution-budget-resource-optimizer.schema.json
examples/agent-execution-budget-resource-optimizer.default.json
tools/validate_agent_execution_budget_resource_optimizers.py
docs/budget-resource-optimizer.md
```

## SVF receipt-state routing consumer

The router may consume Sovereign Validation Fabric validation state as an input to routing posture. It may constrain model lane, autonomy ceiling, fallback posture, and deterministic verification requirements.

It does not define SVF validity, execute validations, issue or verify receipts, mutate policy, or promote advisory validation to blocking validation.

Contract and example:

```text
docs/SVF_RECEIPT_STATE_CONSUMER.md
examples/svf-receipt-state-routing-policy.default.json
tools/validate_svf_receipt_state_routing.py
```

For `selected_missing_observation`, the router must preserve `validation_observation_missing`, deny high-end/pro escalation, require deterministic verification, and keep autonomy constrained to report-only behavior.

## Default local posture

The first SourceOS local profiles are:

```text
urn:srcos:model-profile:local-llama32-1b
urn:srcos:model-profile:local-llama32-3b
```

The 1B profile is the laptop-safe router/triage/summarization default. The 3B profile is the quality fallback when local resources allow it.

## Policy invariants

- Local-first routing is default.
- Prompt egress is denied by default.
- Hosted fallback requires policy approval.
- Per-user personalization requires consent and a model-governance-ledger contract.
- High-end/pro agent execution lanes are denied unless an allowed escalation reason and receipt exist.
- Routine execution de-escalates to standard or cheaper lanes after planning.
- Verification defaults to deterministic tools rather than another expensive model call.
- Budget, quota, resource, latency, and provider-health constraints are evaluated before route execution.
- Missing required optimizer signals fail closed.
- Missing SVF validation observations constrain autonomy and premium model escalation.
- Unknown premium quota denies high-end/pro use.
- Exhausted budget denies or downgrades according to policy rather than silently overrunning.
- Evidence records route decisions, escalation receipts, budget decisions, resource snapshots, quota snapshots, candidate sets, runtime health, cost class, context policy, tool policy, and governance references.
- Prompt evidence should be hash-only by default.
- Model availability is not authorization.
- Production routing requires admitted or review-gated runtime/provider/model evidence.

## Boundary

| Repo | Responsibility |
|---|---|
| `SourceOS-Linux/sourceos-model-carry` | Local model profiles, service refs, local resource posture, and evidence collectors. |
| `SocioProphet/model-governance-ledger` | Per-user consent, data boundary, evaluation, promotion, revocation, model-routing escalation receipts, cost-class evidence, budget/resource audit trails, and model/runtime Trust Chain bindings. |
| `SociOS-Linux/socios` | Opt-in orchestration for personalization workflows. |
| `SocioProphet/model-router` | Runtime route binding, agent execution model-routing policy, budget/resource optimization, SVF receipt-state consumption, Trust Chain route decisions, and policy-aware target selection. |
| `SocioProphet/agentplane` | Execution-chain evidence and run/replay artifacts for routed agent work. |
| `SocioProphet/guardrail-fabric` | Fail-closed policy decisions for tool hooks, model-lane escalation, budget/resource constraints, Trust Chain action admission, and write/network gates. |
| `SocioProphet/policy-fabric` | Policy packaging, inheritance, validation, release review, and budget/resource constraint governance. |
| `SocioProphet/prophet-platform` | Composes final platform admission responses. |

## Validation

```bash
python3 tools/validate_local_personal_route_bindings.py
python3 tools/validate_agent_execution_model_routing_policies.py
python3 tools/validate_agent_execution_budget_resource_optimizers.py
python3 tools/validate_svf_receipt_state_routing.py
python3 tools/validate_trust_chain_model_route_decision.py
make validate-svf-receipt-state-routing
make validate-trust-chain-model-route-decision
```
