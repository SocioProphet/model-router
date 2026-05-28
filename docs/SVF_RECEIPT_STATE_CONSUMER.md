# SVF Receipt-State Consumer

Status: consumer contract doctrine  
Plane: model-router / routing policy consumer  
Upstream authority: SocioProphet/ProCybernetica SVF policy primitive  
Workspace registry: SocioProphet/sociosphere SVF workspace registry

## Purpose

This document defines how `model-router` consumes Sovereign Validation Fabric (SVF) validation state.

The model router may use validation state to choose verification depth, model lane, fallback posture, and autonomy limits. It must not define validity, issue receipts, run SVF Actions, mutate policies, or promote advisory validation to blocking validation.

## Placement

`model-router` owns runtime route binding, agent execution model-routing policy, budget/resource optimization, and policy-aware target selection. SVF receipt-state consumption fits that same boundary: route decisions may consider validation evidence, but authority remains upstream.

## Inputs

The first receipt-state consumer may read a normalized summary with:

- repo;
- ref;
- selected Plan ids;
- Plan modes;
- required observations;
- observed validation commands;
- receipt references;
- missing-observation warnings;
- validation age;
- validation status.

The first tranche is fixture-backed only.

## Routing influence

Validation state may influence:

- whether an agent step may use a higher-autonomy lane;
- whether high-end/pro model lanes remain denied;
- whether deterministic verification is required before model escalation;
- whether the route must downgrade to advisory/report-only behavior;
- whether a PR-readiness summary must preserve `validation_observation_missing`.

Validation state must not:

- bypass guardrail-fabric;
- override policy-fabric;
- create or verify receipts;
- execute Sociosphere runner commands;
- certify downstream repository behavior;
- convert advisory validation into blocking validation;
- infer production readiness from contract validation.

## Initial statuses

The first contract recognizes:

- `validated` — matching observed evidence or receipt reference exists;
- `selected_missing_observation` — a Plan was selected but no observation is attached;
- `not_configured` — no applicable SVF profile or Plan exists;
- `failed` — attached validation evidence reports failure;
- `stale` — validation evidence exists but exceeds the accepted age window.

## Policy consequence

For `selected_missing_observation`, the router must keep high-autonomy and high-cost escalation constrained. It may choose cheaper deterministic or local verification lanes, or report-only behavior, but it must not claim validation success.

For `validated`, the router may treat validation as one advisory signal among policy, budget, privacy, provider health, and task reversibility. It still does not define validity.

## Non-claims

This document does not implement model execution.

This document does not define SVF authority.

This document does not issue or verify receipts.

This document does not grant agent autonomy.
