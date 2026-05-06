# Agent Execution Model Routing Policy

This document defines the canonical model-routing policy for SocioProphet agent execution chains.

The objective is simple: stop spending high-end model capacity on routine work. High-end reasoning is a governed decision lane, not the default execution substrate.

## Policy rule

Use the cheapest lane that can safely complete the next irreversible decision.

That rule applies to each stage of an agent chain independently. The routing decision is not made once for the whole task. It is made for intake, retrieval, planning, execution, verification, review, and finalization.

## Canonical lanes

| Lane | Intended use | Not allowed for |
|---|---|---|
| `no-model` | deterministic shell, grep, tests, linters, formatters, schema validation | semantic judgment |
| `local-cheap` | local routing, short summaries, log triage, first-pass classification | final security or architecture decisions |
| `cheap` | formatting, boilerplate, rewriting, short summaries, simple issue/PR drafting | high-stakes judgment |
| `standard` | normal coding, tests, docs, repo-local refactors, straightforward debugging | prolonged wandering after a plan exists |
| `high-end` | architecture, hard debugging, security review, cross-repo migration, conflicting evidence | chores, formatting, boilerplate, routine implementation |
| `pro` | rare release-blocking or research-grade synthesis | routine coding, drafting, summarization |

## Execution-chain pattern

The default execution chain is:

```text
intake/classify cheap → plan standard/high-end if justified → execute standard/cheap → verify mechanically → review standard/high-end if risk requires → finalize cheap
```

The expensive lane should usually appear only around plan, review, or exceptional debugging. After a high-end plan is produced, execution must de-escalate unless the execution itself is the hard reasoning work.

## Escalation gates

High-end or pro lanes require an escalation receipt with at least one allowed reason:

- architecture decision
- hard debugging
- security review
- privacy review
- multi-repo migration
- irreversible production decision
- high-stakes synthesis
- conflicting evidence resolution
- repeated standard-lane failure
- release gate review

If there is no allowed reason, the policy result is `defer` or `deny`, and the route should be downgraded.

## Context policy

Agent clients and execution chains must avoid token waste by default:

- clear context on task switch
- compact before context pressure becomes acute
- reference file paths instead of pasting large files
- trim logs by default
- redact secrets
- disable noncritical connectors by default
- store prompt evidence as hash-only unless explicitly approved otherwise

## Tool policy

Tools are not free. Network tools, connector tools, and repository write tools must be treated as capability activations.

- tools are off unless needed
- network tools require a reason
- write tools require evidence
- repo mutation requires a branch or explicit direct-commit reason
- mechanical verification is required before an agent run is considered complete

## Enforcement boundary

This repo owns the model-routing policy contract. Enforcement is expected across:

- `SocioProphet/model-router` for route decision and lane selection
- `SocioProphet/guardrail-fabric` for fail-closed hook decisions
- `SocioProphet/agentplane` for execution-chain evidence and run artifacts
- `SocioProphet/model-governance-ledger` for receipts, escalation evidence, and audit trails
- `SocioProphet/policy-fabric` for policy packaging, release review, and inheritance

## Machine-readable contract

The machine-readable policy is defined here:

```text
schemas/agent-execution-model-routing-policy.schema.json
examples/agent-execution-model-routing-policy.default.json
tools/validate_agent_execution_model_routing_policies.py
```

Validate it with:

```bash
python3 tools/validate_agent_execution_model_routing_policies.py
```

## Non-negotiables

1. High-end models are denied by default.
2. Hosted fallback is policy-gated.
3. Routine execution does not escalate above standard without an explicit reason.
4. Verification defaults to deterministic tools, not another expensive model call.
5. Every high-end/pro route emits escalation evidence.
6. Prompt evidence is hash-only by default.
7. After a high-end plan is produced, execution de-escalates by default.
