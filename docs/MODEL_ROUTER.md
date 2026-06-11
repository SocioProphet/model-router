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
