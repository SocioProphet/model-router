# Professional Intelligence Routing

## Purpose

This document defines the first Model Router contract surface for Professional Intelligence OS Gate 3.

Model Router owns routing decisions for local, hosted, service, and fallback model/service paths. It does not own agent authority, policy decisions, workspace UX, memory context, or model governance records. It consumes those references and emits route decisions that can be validated and used as evidence.

## Contract surface

The routing-decision schema lives at:

- `schemas/professional-intelligence-routing-decision.schema.json`

Seed examples live at:

- `examples/professional-intelligence/routing-decision.review-packet.example.json`
- `examples/professional-intelligence/routing-decision.policy-sensitive-summary.example.json`

## Validation

Validate locally:

```bash
python -m pip install jsonschema
python scripts/validate_professional_intelligence_routing.py
```

The workflow `.github/workflows/professional-intelligence-routing.yml` validates the schema and examples when routing artifacts change.

## Control inputs

Routing decisions must account for:

- privacy class;
- latency budget;
- cost ceiling;
- minimum quality score;
- evidence requirement;
- local preference;
- hosted-model allowance;
- policy decision references;
- fallback route requirements.

## Gate 3 role

This routing surface supports the Professional Intelligence OS runnable demo slice by connecting:

- Agent Registry authority;
- Policy Fabric policy decisions;
- Memory Mesh context packs;
- Sherlock search packets;
- Prophet Workspace workrooms;
- Model Governance Ledger evidence;
- Agentplane workflow execution.

## Non-goals

- Do not call live providers from examples.
- Do not store secrets, tokens, prompts, or credentials.
- Do not mark a hosted route as allowed when policy or privacy constraints disallow it.
- Do not emit a selected route without an allowed fallback route.
