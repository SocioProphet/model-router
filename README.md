# model-router

Governed model and service routing for SocioProphet: local vs hosted, small vs large, cost, latency, quality, privacy, fallback, personalization, and eval-confidence policy.

## Role

`model-router` decides where a request should go. It does not own model lifecycle, local model carry profiles, or per-user personalization consent.

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
- Evidence records route decisions, escalation receipts, runtime health, cost class, context policy, tool policy, and governance references.
- Prompt evidence should be hash-only by default.

## Boundary

| Repo | Responsibility |
|---|---|
| `SourceOS-Linux/sourceos-model-carry` | Local model profiles and service refs. |
| `SocioProphet/model-governance-ledger` | Per-user consent, data boundary, evaluation, promotion, revocation, and model-routing escalation receipts. |
| `SociOS-Linux/socios` | Opt-in orchestration for personalization workflows. |
| `SocioProphet/model-router` | Runtime route binding, agent execution model-routing policy, and policy-aware target selection. |
| `SocioProphet/agentplane` | Execution-chain evidence and run/replay artifacts for routed agent work. |
| `SocioProphet/guardrail-fabric` | Fail-closed policy decisions for tool hooks, model-lane escalation, and write/network gates. |
| `SocioProphet/policy-fabric` | Policy packaging, inheritance, validation, and release review. |

## Validation

```bash
python3 tools/validate_local_personal_route_bindings.py
python3 tools/validate_agent_execution_model_routing_policies.py
```
