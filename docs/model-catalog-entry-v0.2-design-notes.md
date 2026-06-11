# model-catalog-entry v0.2 Design Notes

Tracks known v0.1 design debt for the `model-catalog-entry.v0.1.schema.json` schema.
These are intentional deferred items — not bugs — gated on a coordinated v0.2 schema bump.

---

## Issue 1: `base` kind logically doesn't need `baseBinding`

### The debt

`model-catalog-entry.v0.1.schema.json` requires `baseBinding` at the root level for all
entry kinds:

```json
"required": ["id", "version", ..., "baseBinding", ...]
```

The `baseBinding` object exists to point an adapter, steering, or guardrail entry at its
parent base model (`baseModelId`, `baseVersion`, `baseContentHash`). For `kind: "base"`,
this relationship is self-referential: the entry IS the base, so there is no parent to
point at.

The v0.1 validator already acknowledges this: it skips the `baseModelId` required check
when `kind === "base"` (see `tools/validate_model_catalog_entry.py`, gate 3). The
TypeScript contract also calls this out with a comment: `baseModelId optional for
kind="base"; required otherwise`.

But the JSON Schema does not express this constraint — it requires `baseBinding` (with
`baseVersion` and `baseContentHash`) from all entries regardless of `kind`. The
`noetica-chat.synthetic.json` example works around this by providing a `baseBinding`
whose `baseVersion` and `baseContentHash` duplicate the entry's own `version` and
`artifact.contentHash` — semantically redundant values that exist only to satisfy the
schema.

### The v0.2 fix

Replace the unconditional `baseBinding` required constraint with a JSON Schema `if/then`
conditional:

```json
"if": {
  "properties": { "kind": { "const": "base" } }
},
"then": {
  "properties": {
    "baseBinding": {
      "type": "object",
      "required": [],
      "description": "Omit or leave empty for base entries — no parent base exists."
    }
  }
},
"else": {
  "required": ["baseBinding"],
  "properties": {
    "baseBinding": {
      "required": ["baseModelId", "baseVersion", "baseContentHash"]
    }
  }
}
```

This makes `baseBinding` optional for `kind: "base"` and fully required (including
`baseModelId`) for adapter/steering/guardrail kinds. The validator gate 3 can then be
simplified: the schema itself enforces the distinction, so the explicit Python `kind !=
"base"` branch is no longer needed.

### Gate for the fix

Do not create `model-catalog-entry.v0.2.schema.json` until:

1. At least one real `kind: "base"` entry exists in the examples directory with a
   confirmed `artifact.contentHash` — this provides the concrete fixture to validate
   against and removes the synthetic self-referential `baseBinding` values
2. All consuming repos (prophet-platform, model-governance-ledger, prophet-cli `prophet
   model route` facade) are confirmed ready to accept the v0.2 schema path

### Current state

`kind: "base"` entries currently carry a semantically redundant `baseBinding`. All
tooling passes. No action required until the v0.2 gate condition above is met.

---

*Cross-reference: [`MODEL_ROUTER.md`](MODEL_ROUTER.md), [`docs/v0.2-breaking-change-policy.md`](../functional-model-surfaces/docs/v0.2-breaking-change-policy.md)*
