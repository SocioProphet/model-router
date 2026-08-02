# Model Router

Model Router emits governed model and service route decisions for SocioProphet model fabric.

It is not a provider SDK and does not execute model calls. The first slice is deterministic and local-only: it evaluates candidate metadata against a route policy and emits a decision record that downstream ledgers, guardrails, agents, and platform records can reference.

## Role in model fabric

- `functional-model-surfaces` owns the normative model-fabric object model.
- `model-router` owns route decision emission.
- `guardrail-fabric` owns guardrail decision hooks.
- `model-governance-ledger` owns evidence, promotion, rollback, and factsheet records.
- `agent-registry` owns agent/tool authority context.
- `prophet-cli` delegates `prophet model route` here once the binary exists.
- `SourceOS` consumes approved service and model references only; it must not own mutable model lifecycle authority.

## Route dimensions

The first route decision considers:

- task support;
- local vs hosted locality;
- small vs large size class;
- cost tier;
- latency tier;
- quality tier;
- privacy mode;
- fallback policy;
- eval confidence;
- guardrail compatibility.

## Runtime authorization enforcement

The invariant `model_availability_is_not_authorization` is enforced **at route time**, not only in CI. Before any candidate is scored, selected, or returned, `route()` consults the same authorization mirror the CI conformance gate reads (`contracts/prophet-mesh/model-route-authorization.v0.1.json`) via `is_route_authorized`:

- A candidate declares its governed identity with `governanceRoute` (the route id used by the authorization mirror). A candidate without one is denied (fail-closed — an unidentified model cannot be authorized).
- A candidate whose governance route has no evidence-backed `authorized` ledger record is moved to `blockedCandidateRefs` with reason `unauthorized-unledgered-model` and can never be selected, even if it scores highest and is policy-eligible.
- After selection, `route()` re-asserts authorization on the exact model about to be dispatched and raises rather than emit an unauthorized decision — a control that cannot silently pass.

Authorization source precedence: explicit `authorization` argument > request `spec.authorizationRef` > the canonical prophet-mesh contract (the production source of truth). A caller that supplies nothing still gets fail-closed enforcement. Only `model-governance-ledger` (see `SocioProphet/model-governance-ledger#29`) can grant authorization; this router only denies or honors it.

## Current safety boundary

This repository must not store prompts, secrets, datasets, model weights, provider credentials, or live provider calls.

The first implementation emits local deterministic JSON only.

## v0.2 design notes

See [`docs/model-catalog-entry-v0.2-design-notes.md`](model-catalog-entry-v0.2-design-notes.md) for tracked schema design debt and the gate conditions for a v0.2 bump.

## Validation

```bash
make validate
make emit-demo-decision
make test
```
