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
- Evidence records route decisions, runtime health, and governance references.
- Prompt evidence should be hash-only by default.

## Boundary

| Repo | Responsibility |
|---|---|
| `SourceOS-Linux/sourceos-model-carry` | Local model profiles and service refs. |
| `SocioProphet/model-governance-ledger` | Per-user consent, data boundary, evaluation, promotion, revocation. |
| `SociOS-Linux/socios` | Opt-in orchestration for personalization workflows. |
| `SocioProphet/model-router` | Runtime route binding and policy-aware target selection. |

## Validation

```bash
python3 tools/validate_local_personal_route_bindings.py
```
