# Agent Execution Budget and Resource Optimizer

This document defines the optimization layer that sits beside the agent execution model-routing policy.

The routing policy defines what lanes are allowed. The optimizer decides which allowed lane should be selected given budget, quota, resource availability, latency, quality floor, privacy, and operational constraints.

## Operating rule

Select the cheapest acceptable lane subject to:

1. policy compliance
2. privacy and prompt-egress boundaries
3. safety and task risk
4. required quality floor
5. budget ceiling
6. live local resource availability
7. provider quota and health
8. latency constraints
9. deterministic verification availability

Cost is optimized only after hard policy, privacy, safety, and quality constraints are satisfied.

## Why this is separate from routing policy

`AgentExecutionModelRoutingPolicy` answers: which model lanes may be used for this class of work?

`AgentExecutionBudgetResourceOptimizer` answers: among the allowed candidates, which lane is best right now?

The separation matters because the same task can route differently depending on live constraints:

- local model unavailable or unhealthy
- device thermal/battery pressure
- insufficient memory for a local model
- hosted provider quota near exhaustion
- provider latency/error rate elevated
- daily/session budget pressure
- critical task requiring a quality floor
- network unavailable or disallowed

## Candidate selection loop

The expected decision loop is:

```text
classify task and stage
load routing policy
load optimizer policy
collect resource/quota/budget signals
construct candidate lane set
remove lanes blocked by hard policy
remove lanes below quality floor
remove lanes exceeding budget/quota/resource constraints
rank candidates by configured tie-breakers
emit route + budget/resource evidence
execute only after route decision
```

The default candidate order is:

```text
no-model → local-cheap → cheap → standard → high-end → pro
```

The router must never silently upgrade to a more expensive lane. Upgrades require a reason and evidence.

## Budget policy

The default optimizer defines task, session, and daily windows. It caps high-end/pro share and reserves premium capacity for real escalation events.

Default pressure response is `downgrade`. If budget is exhausted, enforcement denies rather than silently exceeding the ceiling.

The intended policy posture is:

- high-end and pro lanes are scarce capacity
- reserve premium lanes for architecture, security, hard debugging, and release gates
- prefer downgrade/defer over silent overspend
- record every budget decision

## Resource policy

The optimizer requires live signals before routing:

- local model profile availability
- local service health
- battery state
- thermal state
- available memory
- network availability
- provider quota remaining
- provider error rate
- provider p95 latency
- estimated input/output tokens

Local model use is preferred when healthy, but denied under critical thermal/battery state or insufficient memory. Hosted use requires policy, network, known quota, and acceptable provider health.

## Quality floors

The default risk floors are:

| Risk class | Minimum lane | Verification |
|---|---|---|
| low | local-cheap | optional |
| medium | standard | required |
| high | high-end | required |
| critical | pro | required |

The key constraint is that budget cannot push a critical or high-risk decision below its required quality floor. Conversely, quality preference cannot exceed budget or policy ceilings without explicit approval.

## Evidence requirements

Every optimized route must emit:

- budget decision
- resource snapshot
- quota snapshot
- candidate set
- selected candidate
- prompt evidence mode, hash-only by default

This evidence should flow into AgentPlane run/session artifacts, Guardrail Fabric decisions, and Model Governance Ledger receipts.

## Machine-readable contract

```text
schemas/agent-execution-budget-resource-optimizer.schema.json
examples/agent-execution-budget-resource-optimizer.default.json
tools/validate_agent_execution_budget_resource_optimizers.py
```

Validate it with:

```bash
python3 tools/validate_agent_execution_budget_resource_optimizers.py
```

## Non-negotiables

1. Missing required signals fail closed.
2. Unknown premium quota denies high-end/pro use.
3. Exhausted budget denies rather than silently overruns.
4. Hosted fallback still requires policy.
5. Local model use is preferred only when the local service is healthy and resource-safe.
6. The optimizer never silently upgrades to a more expensive lane.
7. Prompt evidence remains hash-only by default.
