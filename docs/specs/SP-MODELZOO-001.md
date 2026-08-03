# SP-MODELZOO-001 — Community Model Zoo
### Roadmap Phase 6 build spec: a governed model registry aligned to the SourceOS models we ship AND the enterprise models we identified.

| Field | Value |
|---|---|
| Spec ID | `SP-MODELZOO-001` · v0.1.0 DRAFT · **E1** |
| Depends on | `model-router` (`model-catalog-entry.v0.1`), `SP-DATALAKE-001` (lake = training/eval data), the unified **DecisionLedgerEntry** (promotion spine), `prophet-ai-eval`, catalog-seed promotion_state pattern |
| Consumers | Phase 7 (Community Prophet / EBA central AI), the domain workspaces, agent-execution routing |
| Home | `model-router` (owns the model catalog); this spec = its Zoo layer |

## 0. Objective
A **Community Model Zoo**: one governed registry that holds **both** tiers under a single schema, so routing, eval, governance, and the IBM→open competitive map are all one surface — not two.
- **Tier S — SourceOS-shipped** (what we serve): base open-weights + `sourceos.*`/`noetica.*` adapters, steering, guardrails. Already exists as `model-router/model-catalog-entry.v0.1`; the Zoo *consumes* it, does not fork it.
- **Tier E — Enterprise-identified** (what we benchmark against / can adapt): the watsonx family from the IBM open-stack teardown, registered as **reference/adapter_candidate** with the IBM→open mapping — competitive/reference, **not admitted-for-serving** unless it passes the same gates.

**Alignment is the point:** a model's tier is just its `promotion_state`; both tiers share `model-catalog-entry` fields (interpretability, governance, attestation, evaluation, egress, lifecycle) and the same promotion ledger.

## 1. Tier S — SourceOS models we ship (consume `model-catalog-entry.v0.1`)
`kind ∈ {base, adapter, steering, guardrail}`; `baseBinding = {baseModelId, baseVersion, baseContentHash}`.
| id (namespace) | kind | base weights (baseBinding) |
|---|---|---|
| `sourceos.base.*` | base | gemma-2-9b-it · llama-3.2-1b/3b · deepseek-v3 · qwen3-32b/235b-a22b · phi |
| `sourceos.adapter.summarize.v1` | adapter | on a base |
| `sourceos.steering.concept-suppressor.v1` | steering | gemma-scope SAE features |
| `sourceos.guardrail.*` | guardrail | policy/ontology-bound |
| `noetica.chat.m2a` | base/adapter | noetica-impair (gemma-2-9b-it L20 rig) |
Governance already carried: `guardrailPolicyRef`, `ontologyRef`, interpretability, attestation, evaluation, egress, lifecycle.

## 2. Tier E — Enterprise models we identified (from the IBM teardown → open)
Registered as `promotion_state: reference` (competitive) or `adapter_candidate`; each carries the sovereign-open mapping so "recreate it" is a WO, not a wish.
| Enterprise (identified) | Capability | Sovereign-open target | Zoo state |
|---|---|---|---|
| watsonx.ai | served foundation models (Granite family) | vLLM/KServe over Tier-S base weights | reference |
| watsonx.governance | model governance / factsheets | our `model-catalog-entry.governance` + DecisionLedger | **already ours** |
| watsonx.data | lakehouse for training | SP-DATALAKE-001 (Iceberg/Trino) | reference |
| watsonx.orchestrate | agent orchestration | AgentPlane / sp-orchestrator | reference |
| watsonx-code-assistant | code models | Tier-S adapter | adapter_candidate |
| watsonx-bi / data-intelligence | semantic BI / catalog | semantic-search-bi + prophet-core-catalog | reference |
| Prometheus (eval) | LLM-judge eval | prophet-ai-eval | adapter_candidate |
Each Tier-E entry is **benchmark-only** until it passes §4 gates and a Michael-signed promotion.

## 3. Work orders
| WO | Title | Depends | Acceptance |
|---|---|---|---|
| `WO_MZ_001` | **Binding.** Read `model-router/model-catalog-entry.v0.1` + SP-DATALAKE bindings; emit `BINDING.md`. | — | 100% symbol coverage. |
| `WO_MZ_002` | **Zoo registry.** Add `promotion_state {reference, adapter_candidate, admitted, tombstoned}` + `tier {S,E}` to `model-catalog-entry`; the Zoo is the set of entries. | 001 | Tier-S admitted entries serve; Tier-E entries are `reference` and cannot route. |
| `WO_MZ_003` | **Enterprise reference load.** Register the watsonx-family Tier-E entries with the IBM→open mapping (§2). | 002 | Every enterprise model has a sovereign-open target + eval baseline; none is `admitted`. |
| `WO_MZ_004` | **Governed promotion.** A model promotes reference→adapter_candidate→admitted only when interpretability + attestation + eval + guardrail gates pass, each emitting a **DecisionLedgerEntry**; `admitted` requires Michael sign-off. | 002 | An un-evaluated model cannot reach `admitted`; every promotion has a ledger entry + witness. |
| `WO_MZ_005` | **Lake-fed eval.** `prophet-ai-eval` reads SP-DATALAKE tables as eval sets; results attach to the catalog entry's `evaluation`. | 002, SP-DATALAKE-001 WO_DL_003 | A model's eval provenance traces to a pinned lake table (ledgered read). |
| `WO_MZ_006` | **Route + serve.** `model-router` routes only over `admitted` Zoo entries; trust-chain route decision carries the entry's governance. | 004 | Routing to a non-admitted entry is refused with a decision. |

## 4. Invariants
- **MZ-INV-1 (one schema, two tiers).** Both tiers are `model-catalog-entry` records; tier = `promotion_state`+`tier`. No parallel enterprise registry.
- **MZ-INV-2 (reference ≠ served).** A `reference`/Tier-E entry can never be routed to; only `admitted` serves. (Keeps enterprise benchmarks out of the serving path.)
- **MZ-INV-3 (ledgered promotion).** Every promotion emits a signed DecisionLedgerEntry with interpretability + attestation + eval witnesses; `admitted` needs Michael sign-off.
- **MZ-INV-4 (eval provenance).** Every `evaluation` result traces to a pinned SP-DATALAKE table (ledgered read) — no unprovenanced scores.
- **MZ-INV-5 (governance carried).** No entry without `guardrailPolicyRef` + `ontologyRef` + `egress`; enterprise entries inherit the same bar.

## 5. Why this alignment matters
The IBM teardown priced watsonx as "our replacement = 0." This Zoo makes the enterprise models **first-class reference entries in the same registry as our shipped models**, with the open target and the eval baseline attached — so "close the gap" is a per-model promotion (reference → adapter_candidate → admitted) under one governed ledger, and `watsonx.governance` is revealed as something we *already have* (the `model-catalog-entry.governance` + DecisionLedger). Feeds Phase 7: the Community Prophet (EBA central AI) routes over the `admitted` Zoo.
